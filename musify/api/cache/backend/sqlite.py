from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping, Callable
from datetime import datetime, timedelta
from os.path import splitext, dirname, join
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Self, AsyncContextManager

from dateutil.relativedelta import relativedelta
from requests import Request, PreparedRequest, Response

from musify import PROGRAM_NAME
from musify.api.cache.backend.base import DEFAULT_EXPIRE, ResponseCache, ResponseRepository, RepositoryRequestType
from musify.api.cache.backend.base import RequestSettings, PaginatedRequestSettings
from musify.api.exception import CacheError
from musify.utils import required_modules_installed

try:
    import aiosqlite
except ImportError:
    aiosqlite = None

REQUIRED_MODULES = [aiosqlite]


class SQLiteTable[K: tuple[Any, ...], V: str](ResponseRepository[K, V], AsyncContextManager[aiosqlite.Connection]):

    __slots__ = ()

    #: The column under which a response's name is stored in the table
    name_column = "name"
    #: The column under which response data is stored in the table
    data_column = "data"
    #: The column under which the response cache time is stored in the table
    cached_column = "cached_at"
    #: The column under which the response expiry time is stored in the table
    expiry_column = "expires_at"

    @classmethod
    async def create(
            cls,
            connection: aiosqlite.Connection,
            settings: RequestSettings,
            expire: timedelta | relativedelta = DEFAULT_EXPIRE,
    ) -> SQLiteTable:
        if not connection.is_alive():
            await connection

        repository = cls(connection=connection, settings=settings, expire=expire)

        ddl_sep = "\t, "
        ddl = "\n".join((
            f"CREATE TABLE IF NOT EXISTS {repository.settings.name} (",
            "\t" + f"\n{ddl_sep}".join(
                f"{key} {data_type} NOT NULL" for key, data_type in repository._primary_key_columns.items()
            ),
            f"{ddl_sep}{repository.name_column} TEXT",
            f"{ddl_sep}{repository.cached_column} TIMESTAMP NOT NULL",
            f"{ddl_sep}{repository.expiry_column} TIMESTAMP NOT NULL",
            f"{ddl_sep}{repository.data_column} TEXT",
            f"{ddl_sep}PRIMARY KEY ({", ".join(repository._primary_key_columns)})",
            ");",
            f"CREATE INDEX IF NOT EXISTS idx_{repository.expiry_column} "
            f"ON {repository.settings.name}({repository.expiry_column});"
        ))

        repository.logger.debug(f"Creating {repository.settings.name!r} table with the following DDL:\n{ddl}")
        await repository.connection.executescript(ddl)
        await repository.commit()

        return repository

    def __init__(
            self,
            connection: aiosqlite.Connection,
            settings: RequestSettings,
            expire: timedelta | relativedelta = DEFAULT_EXPIRE,
    ):
        required_modules_installed(REQUIRED_MODULES, self)

        super().__init__(settings=settings, expire=expire)

        self.connection = connection

    async def __aenter__(self) -> Self:
        if not self.connection.is_alive():
            await self.connection.__aenter__()
        return self

    async def __aexit__(self, __exc_type, __exc_value, __traceback) -> None:
        await self.connection.__aexit__(__exc_type, __exc_value, __traceback)

    async def commit(self) -> None:
        await self.connection.commit()

    async def close(self) -> None:
        await self.commit()
        await self.connection.close()

    @property
    def _primary_key_columns(self) -> Mapping[str, str]:
        """A map of column names to column data types for the primary keys of this repository."""
        keys = {"method": "VARCHAR(10)", "id": "VARCHAR(50)"}
        if isinstance(self.settings, PaginatedRequestSettings):
            keys["offset"] = "INT2"
            keys["size"] = "INT2"

        return keys

    def get_key_from_request(self, request: RepositoryRequestType[K]) -> K | None:
        if isinstance(request, Response):
            request = request.request
        if not isinstance(request, Request | PreparedRequest):
            return request  # `request` is the key

        id_ = self.settings.get_id(request.url)
        if not id_:
            return

        key = [str(request.method), id_]
        if isinstance(self.settings, PaginatedRequestSettings):
            key.append(self.settings.get_offset(request.url))
            key.append(self.settings.get_limit(request.url))

        return tuple(key)

    async def count(self, expired: bool = True) -> int:
        query = f"SELECT COUNT(*) FROM {self.settings.name}"
        params = []

        if not expired:
            query += f"\nWHERE {self.expiry_column} > ?"
            params.append(datetime.now().isoformat())

        async with self.connection.execute(query, params) as cur:
            row = await cur.fetchone()

        return row[0]

    async def contains(self, request: RepositoryRequestType[K]) -> bool:
        key = self.get_key_from_request(request)
        query = "\n".join((
            f"SELECT COUNT(*) FROM {self.settings.name}",
            f"WHERE {self.expiry_column} > ?",
            f"\tAND {"\n\tAND ".join(f"{key} = ?" for key in self._primary_key_columns)}",
        ))
        async with self.connection.execute(query, (datetime.now().isoformat(), *key)) as cur:
            rows = await cur.fetchone()
        return rows[0] > 0

    async def __aiter__(self):
        query = "\n".join((
            f"SELECT {", ".join(self._primary_key_columns)}, {self.data_column} ",
            f"FROM {self.settings.name}",
            f"WHERE {self.expiry_column} > ?",
        ))
        async with self.connection.execute(query, (datetime.now().isoformat(),)) as cur:
            async for row in cur:
                yield row[:-1], row[-1]

    async def get_response(self, request: RepositoryRequestType[K]) -> V | None:
        key = self.get_key_from_request(request)
        if not key:
            return

        query = "\n".join((
            f"SELECT {self.data_column} FROM {self.settings.name}",
            f"WHERE {self.data_column} IS NOT NULL",
            f"\tAND {self.expiry_column} > ?",
            f"\tAND {"\n\tAND ".join(f"{key} = ?" for key in self._primary_key_columns)}",
        ))

        async with self.connection.execute(query, (datetime.now().isoformat(), *key)) as cur:
            row = await cur.fetchone()

        if not row:
            return
        return self.deserialize(row[0])

    async def _set_item_from_key_value_pair(self, __key: K, __value: Any) -> None:
        columns = (
            *self._primary_key_columns,
            self.name_column,
            self.cached_column,
            self.expiry_column,
            self.data_column
        )
        query = "\n".join((
            f"INSERT OR REPLACE INTO {self.settings.name} (",
            f"\t{", ".join(columns)}",
            ") ",
            f"VALUES({",".join("?" * len(columns))});",
        ))
        params = (
            *__key,
            self.settings.get_name(__value),
            datetime.now().isoformat(),
            self.expire.isoformat(),
            self.serialize(__value)
        )

        await self.connection.execute(query, params)

    async def delete_response(self, request: RepositoryRequestType[K]) -> bool:
        key = self.get_key_from_request(request)
        query = "\n".join((
            f"DELETE FROM {self.settings.name}",
            f"WHERE {"\n\tAND ".join(f"{key} = ?" for key in self._primary_key_columns)}",
        ))

        async with self.connection.execute(query, key) as cur:
            count = cur.rowcount
        return count > 0

    def serialize(self, value: Any) -> V | None:
        if isinstance(value, str):
            try:
                json.loads(value)  # check it is a valid json value
            except json.decoder.JSONDecodeError:
                return
            return value

        return json.dumps(value, indent=2)

    def deserialize(self, value: V | dict) -> Any:
        if isinstance(value, dict):
            return value

        try:
            return json.loads(value)
        except (json.decoder.JSONDecodeError, TypeError):
            return


class SQLiteCache(ResponseCache[SQLiteTable], AsyncContextManager):

    __slots__ = ()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def type(cls):
        return "sqlite"

    @staticmethod
    def _get_sqlite_path(path: str) -> str:
        if not splitext(path)[1] == ".sqlite":  # add/replace extension if not given
            path += ".sqlite"
        return path

    @staticmethod
    def _clean_kwargs[T: dict](kwargs: T) -> T:
        kwargs.pop("cache_name", None)
        kwargs.pop("connection", None)
        return kwargs

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls, value: Any, **kwargs) -> Self:
        yield cls.connect_with_path(path=value, **kwargs)

    @classmethod
    @contextlib.asynccontextmanager
    async def connect_with_path(cls, path: str | Path, **kwargs) -> Self:
        """Connect with an SQLite DB at the given ``path`` and return an instantiated :py:class:`SQLiteResponseCache`"""
        path = cls._get_sqlite_path(str(path))
        if dirname(path):
            os.makedirs(dirname(path), exist_ok=True)

        async with aiosqlite.connect(database=path) as connection:
            yield cls(cache_name=path, connection=connection, **cls._clean_kwargs(kwargs))

    @classmethod
    @contextlib.asynccontextmanager
    async def connect_with_in_memory_db(cls, **kwargs) -> Self:
        """Connect with an in-memory SQLite DB and return an instantiated :py:class:`SQLiteResponseCache`"""
        async with aiosqlite.connect(database="file::memory:?cache=shared", uri=True) as connection:
            yield cls(cache_name="__IN_MEMORY__", connection=connection, **cls._clean_kwargs(kwargs))

    @classmethod
    @contextlib.asynccontextmanager
    async def connect_with_temp_db(cls, name: str = f"{PROGRAM_NAME.lower()}_db.tmp", **kwargs) -> Self:
        """Connect with a temporary SQLite DB and return an instantiated :py:class:`SQLiteResponseCache`"""
        path = cls._get_sqlite_path(join(gettempdir(), name))

        async with aiosqlite.connect(database=path) as connection:
            yield cls(cache_name=name, connection=connection, **cls._clean_kwargs(kwargs))

    def __init__(
            self,
            cache_name: str,
            connection: aiosqlite.Connection,
            repository_getter: Callable[[Self, str], SQLiteTable] = None,
            expire: timedelta | relativedelta = DEFAULT_EXPIRE,
    ):
        required_modules_installed(REQUIRED_MODULES, self)

        super().__init__(cache_name=cache_name, repository_getter=repository_getter, expire=expire)

        self.connection = connection

    async def __aenter__(self) -> Self:
        if not self.connection.is_alive():
            await self.connection.__aenter__()
        return self

    async def __aexit__(self, __exc_type, __exc_value, __traceback) -> None:
        await self.connection.__aexit__(__exc_type, __exc_value, __traceback)

    async def close(self):
        await self.connection.commit()
        await self.connection.close()

    async def create_repository(self, settings: RequestSettings) -> SQLiteTable:
        if settings.name in self:
            raise CacheError(f"Repository already exists: {settings.name}")

        repository = await SQLiteTable.create(connection=self.connection, settings=settings, expire=self.expire)
        self._repositories[settings.name] = repository
        return repository
