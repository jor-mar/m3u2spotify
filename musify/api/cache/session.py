import contextlib
from http.client import InvalidURL

from aiohttp import ClientSession, ClientRequest
from aiohttp.typedefs import StrOrURL

from musify.api.cache.backend.base import ResponseCache, ResponseRepository
from musify.api.cache.response import CachedResponse


class CachedSession(ClientSession):
    """
    A modified session which attempts to get/save responses from/to a stored cache before/after sending it.

    :param cache: The cache to use for managing cached responses.
    """

    __slots__ = ("cache",)

    def __init__(self, cache: ResponseCache, **kwargs):
        super().__init__(**kwargs)

        #: The cache to use when attempting to return a cached response.
        self.cache = cache

    @contextlib.asynccontextmanager
    async def request(self, method: str, url: StrOrURL, persist: bool = True, **kwargs):
        """
        Perform HTTP request.

        :param method: HTTP request method (such as GET, POST, PUT, etc.)
        :param url: The URL to perform the request on.
        :param persist: Whether to persist responses returned from sending network requests i.e. non-cached responses.
        :return: Either the :py:class:`CachedResponse` if a response was found in the cache,
            or the :py:class:`ClientResponse` if the request was sent.
        """
        try:
            url = self._build_url(url)
        except ValueError as e:
            raise InvalidURL(url) from e

        req = ClientRequest(
            method=method,
            url=url,
            loop=self._loop,
            response_class=self._response_class,
            session=self,
            trust_env=self.trust_env,
            **kwargs,
        )

        repository = self.cache.get_repository_from_requests(req.request_info)
        response = await self._get_cached_response(req, repository=repository)
        if response is None:
            response = await super().request(method=method, url=url, **kwargs)

        yield response

        if persist and not isinstance(response, CachedResponse):
            await repository.save_response(response)

    async def _get_cached_response(
            self, request: ClientRequest, repository: ResponseRepository | None
    ) -> CachedResponse | None:
        if repository is None:
            return

        data = await repository.get_response(request)
        if data is None:
            return

        if not isinstance(data, str | bytes):
            repository = self.cache.get_repository_from_url(request.url)
            data = repository.serialize(data)

        return CachedResponse(request=request, data=data)
