from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Iterable, MutableMapping
from copy import copy
from typing import Any, Self

from syncify.abstract.collection import ItemCollection, Album
from syncify.abstract.item import Item
from syncify.spotify import APIMethodInputType
from syncify.spotify.base import SpotifyObject
from syncify.spotify.enums import IDType, ItemType
from syncify.spotify.exception import SpotifyIDTypeError
from syncify.spotify.utils import validate_item_type, convert, extract_ids, get_id_type
from .item import SpotifyTrack, SpotifyArtist, SpotifyItem


# noinspection PyShadowingNames
class SpotifyCollection[T: SpotifyItem](SpotifyObject, ItemCollection[T], metaclass=ABCMeta):
    """Generic class for storing a collection of Spotify tracks."""

    @property
    @abstractmethod
    def items(self):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(
            cls, value: APIMethodInputType, use_cache: bool = True, items: Iterable[T] | None = None
    ) -> Self:
        """
        Generate a new object, calling all required endpoints to get a complete set of data for this item type.

        The given ``value`` may be:
            * A string representing a URL/URI/ID.
            * A MutableSequence of strings representing URLs/URIs/IDs of the same type.
            * A Spotify API JSON response for a collection with a valid ID value under an ``id`` key.
            * A MutableSequence of Spotify API JSON responses for a collection with
                a valid ID value under an ``id`` key.

        When a list is given, only the first item is processed.

        :param value: The value representing some Spotify artist. See description for allowed value types.
        :param use_cache: Use the cache when calling the API endpoint. Set as False to refresh the cached response.
        :param items: Optionally, give a list of available items to build a response for this collection.
            In doing so, the method will first try to find the API responses for the items of this collection
            in the given list before calling the API for any items not found there.
            This helps reduce the number of API calls made on initialisation.
        """

    @classmethod
    def _load_response(cls, value: APIMethodInputType, use_cache: bool = True) -> dict[str, Any]:
        kind = cls.__name__.casefold().replace("spotify", "")
        item_type = ItemType.from_name(kind)
        key = cls.api.collection_types[item_type.name]

        try:  # attempt to get response from the given value alone
            validate_item_type(value, kind=item_type)
            value: dict[str, Any]
            assert len(value[key][cls.api.items_key]) == value[key]["total"]
            return value
        except (ValueError, AssertionError, TypeError):  # reload response from the API
            return cls.api.get_collections(value, kind=item_type, use_cache=use_cache)[0]

    def __getitem__(self, __key: str | int | Item) -> T:
        if isinstance(__key, int):  # simply index the list or items
            return self.items[__key]
        elif isinstance(__key, Item):  # take the URI
            if not __key.has_uri or __key.uri is None:
                raise KeyError(f"Given item does not have a URI associated: {__key.name}")
            __key = __key.uri
            key_type = IDType.URI
        else:  # determine the ID type
            try:
                key_type = get_id_type(__key)
            except SpotifyIDTypeError:
                try:
                    return next(item for item in self.items if item.name == __key)
                except StopIteration:
                    raise KeyError(f"No matching name found: '{__key}'")

        try:  # get the item based on the ID type
            if key_type == IDType.URI:
                return next(item for item in self.items if item.uri == __key)
            elif key_type == IDType.ID:
                return next(item for item in self.items if item.uri.split(":")[2] == __key)
            elif key_type == IDType.URL:
                __key = convert(__key, type_in=IDType.URL, type_out=IDType.URI)
                return next(item for item in self.items if item.uri == __key)
            elif key_type == IDType.URL_EXT:
                __key = convert(__key, type_in=IDType.URL_EXT, type_out=IDType.URI)
                return next(item for item in self.items if item.uri == __key)
            else:
                raise KeyError(f"ID Type not recognised: '{__key}'")
        except StopIteration:
            raise KeyError(f"No matching {key_type.name} found: '{__key}'")


class SpotifyAlbum(SpotifyCollection[SpotifyTrack], Album[SpotifyTrack]):
    """
    Extracts key ``album`` data from a Spotify API JSON response.

    :param response: The Spotify API JSON response
    """

    @property
    def name(self):
        return self.response["name"]

    @property
    def items(self):
        return self.tracks

    @property
    def tracks(self):
        return self._tracks

    @property
    def artists(self):
        return self._artists

    @property
    def artist(self):
        return self._tag_sep.join(artist["name"] for artist in self.response["artists"])

    @property
    def album_artist(self) -> str:
        return self.artist

    @property
    def track_total(self):
        return self.response["total_tracks"]

    @property
    def genres(self):
        return self.response.get("genres", [])

    @property
    def year(self) -> int:
        return int(self.response["release_date"][:4])

    @property
    def compilation(self):
        return self.response["album_type"] == "compilation"

    @property
    def image_links(self):
        images = {image["height"]: image["url"] for image in self.response["images"]}
        return {"cover_front": url for height, url in images.items() if height == max(images)}

    @property
    def has_image(self):
        return len(self.response["images"]) > 0

    @property
    def length(self):
        lengths = {track.length for track in self.tracks}
        return sum(lengths) if lengths else None

    @property
    def rating(self):
        return self.response.get("popularity")

    def __init__(self, response: MutableMapping[str, Any]):
        Album.__init__(self)
        SpotifyObject.__init__(self, response=response)

        album_only = copy(response)
        for track in response["tracks"]["items"]:
            track["album"] = album_only

        self._artists = list(map(SpotifyArtist, response["artists"]))
        self._tracks = list(map(SpotifyTrack, response["tracks"]["items"]))

        for track in self.tracks:
            track.disc_total = self.disc_total

    @classmethod
    def load(cls, value: APIMethodInputType, use_cache: bool = True, items: Iterable[SpotifyTrack] | None = None):
        cls._check_for_api()
        obj = cls.__new__(cls)
        response = cls._load_response(value, use_cache=use_cache)

        if not items:  # no items given, regenerate API response from the URL
            id_ = extract_ids(value)[0]
            obj.response = {"href": convert(id_, kind=ItemType.ALBUM, type_in=IDType.ID, type_out=IDType.URL)}
            obj.reload(use_cache=use_cache)
        else:  # attempt to find items for this album in the given items
            uri_tracks: Mapping[str, SpotifyTrack] = {track.uri: track for track in items}
            uri_get: list[str] = []

            for i, track_raw in enumerate(response["tracks"]["items"]):
                # loop through the skeleton response for this album
                # find items that match from the given items
                track: SpotifyTrack = uri_tracks.get(track_raw["track"]["uri"])
                if track:  # replace the skeleton response with the response from the track
                    track_raw.clear()
                    track_raw |= track.response
                elif not track_raw["is_local"]:  # add to get list
                    uri_get.append(track_raw["uri"])

            if len(uri_get) > 0:  # get remaining items
                tracks_new = cls.api.get_tracks(uri_get, features=True, use_cache=use_cache)
                uri_tracks: Mapping[str, Mapping[str, Any]] = {r["uri"]: r for r in tracks_new}

                for i, track_raw in enumerate(response["tracks"]["items"]):
                    track: Mapping[str, Any] = uri_tracks.get(track_raw["track"]["uri"])
                    if track:  # replace the skeleton response with the new response
                        track_raw.clear()
                        track_raw |= track

            obj.__init__(response)

        return obj

    def reload(self, use_cache: bool = True):
        self._check_for_api()

        # reload with enriched data
        response = self.api.get(self.url, use_cache=use_cache, log_pad=self._url_pad)
        self.api.get_tracks(response["tracks"]["items"], features=True, use_cache=use_cache)

        self.__init__(response)
