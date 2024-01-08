import logging.config
import os
import shutil
from os.path import join, basename, dirname

import pytest
import yaml
from _pytest.fixtures import SubRequest

from syncify import MODULE_ROOT
from syncify.shared.api.request import RequestHandler
from syncify.shared.logger import SyncifyLogger
from syncify.spotify.api import SpotifyAPI
from syncify.spotify.processors.wrangle import SpotifyDataWrangler
from tests.spotify.api.mock import SpotifyMock


# noinspection PyUnusedLocal
@pytest.hookimpl
def pytest_configure(config: pytest.Config):
    """Loads logging config"""
    config_file = join(dirname(dirname(__file__)), "logging.yml")
    with open(config_file, "r") as file:
        log_config = yaml.full_load(file)

    log_config.pop("compact", False)
    SyncifyLogger.disable_bars = True
    SyncifyLogger.compact = True

    for formatter in log_config["formatters"].values():  # ensure ANSI colour codes in format are recognised
        formatter["format"] = formatter["format"].replace(r"\33", "\33")

    log_config["loggers"][MODULE_ROOT] = log_config["loggers"]["test"]
    logging.config.dictConfig(log_config)


@pytest.fixture
def path(request: pytest.FixtureRequest | SubRequest, tmp_path: str) -> str:
    """
    Copy the path of the source file to the test cache for this test and return the cache path.
    Deletes the test folder when test is done.
    """
    if hasattr(request, "param"):
        src_path = request.param
    else:  # assume path is given at the top-level fixture, get param from this request
        # noinspection PyProtectedMember
        src_path = request._pyfuncitem.callspec.params[request._parent_request.fixturename]

    trg_path = join(tmp_path, basename(src_path))

    os.makedirs(dirname(trg_path), exist_ok=True)
    shutil.copyfile(src_path, trg_path)

    yield trg_path

    shutil.rmtree(dirname(trg_path))


@pytest.fixture(scope="session")
def spotify_wrangler():
    """Yields a :py:class:`SpotifyDataWrangler` for testing Spotify data wrangling"""
    return SpotifyDataWrangler()


@pytest.fixture(scope="session")
def spotify_api(spotify_mock: SpotifyMock) -> SpotifyAPI:
    """Yield an authorised :py:class:`SpotifyAPI` object"""
    token = {"access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"}
    api = SpotifyAPI(cache_path=None)
    api.handler = RequestHandler(name=api.source, token=token, cache_path=None)
    return api


@pytest.fixture(scope="session", autouse=True)
def spotify_mock() -> SpotifyMock:
    """Yield an authorised :py:class:`SpotifyMock` object"""
    with SpotifyMock() as m:
        yield m
