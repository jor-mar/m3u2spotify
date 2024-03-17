"""
Implements a :py:class:`RemoteLibrary` for Spotify.
"""

from collections.abc import Collection, Mapping, Iterable
from typing import Any

from musify.shared.core.object import Playlist, Library
from musify.shared.remote.enum import RemoteObjectType
from musify.shared.remote.library import RemoteLibrary
from musify.shared.remote.object import RemoteTrack
from musify.spotify.api import SpotifyAPI
from musify.spotify.factory import SpotifyObjectFactory
from musify.spotify.object import SpotifyTrack, SpotifyAlbum, SpotifyArtist, SpotifyPlaylist


class SpotifyLibrary(RemoteLibrary[SpotifyAPI, SpotifyPlaylist, SpotifyTrack, SpotifyAlbum, SpotifyArtist]):
    """
    Represents a Spotify library. Provides various methods for manipulating
    tracks and playlists across an entire Spotify library collection.
    """
    __attributes_classes__ = RemoteLibrary

    @staticmethod
    def _validate_item_type(items: Any | Iterable[Any]) -> bool:
        if isinstance(items, Iterable):
            return all(isinstance(item, SpotifyTrack) for item in items)
        return isinstance(items, SpotifyTrack)

    def _create_factory(self, api: SpotifyAPI) -> SpotifyObjectFactory:
        return SpotifyObjectFactory(api=api)

    def _filter_playlists(self, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pl_total = len(responses)
        pl_names_filtered = self.playlist_filter({response["name"] for response in responses})
        responses = [response for response in responses if response["name"] in pl_names_filtered]

        self.logger.debug(
            f"Filtered out {pl_total - len(responses)} playlists from "
            f"{pl_total} {self.api.source} available playlists"
            if (pl_total - len(responses)) > 0 else f"{len(responses)} playlists found"
        )

        return responses

    def _get_total_tracks(self, responses: list[dict[str, Any]]) -> int:
        return sum(pl["tracks"]["total"] for pl in responses)

    def enrich_tracks(
            self, features: bool = False, analysis: bool = False, albums: bool = False, artists: bool = False
    ) -> None:
        """
        Enriches the ``features``, ``analysis``, ``albums``, and/or ``artists`` data for currently loaded tracks.

        :param features: Load all audio features (e.g. BPM, tempo, key etc.)
        :param analysis: Load all audio analyses (technical audio data).
            WARNING: can be very slow as calls to this endpoint cannot be batched i.e. one call per track.
        :param albums: Reload albums for all tracks, adding extra album data e.g. genres, popularity
        :param artists: Reload artists for all tracks, adding extra artist data e.g. genres, popularity, followers
        """
        if not self.tracks or not any((features, analysis, albums, artists)):
            return
        self.logger.debug(f"Enrich {self.api.source} tracks: START")
        self.logger.info(
            f"\33[1;95m  >\33[1;97m Enriching {len(self.tracks)} {self.api.source} tracks \33[0m"
        )

        tracks = [track for track in self.tracks if track.has_uri]
        self.api.extend_tracks(tracks, features=features, analysis=analysis, use_cache=self.use_cache)

        # enrich on list of URIs to avoid duplicate calls for same items
        if albums:
            album_uris: set[str] = {track.response["album"]["uri"] for track in self.tracks}
            album_responses = self.api.get_items(
                album_uris, kind=RemoteObjectType.ALBUM, extend=False, use_cache=self.use_cache
            )
            for album in album_responses:
                album.pop("tracks")

            albums = {response["uri"]: response for response in album_responses}
            for track in self.tracks:
                track.response["album"] = albums[track.response["album"]["uri"]]

        if artists:
            artist_uris: set[str] = {artist["uri"] for track in self.tracks for artist in track.response["artists"]}
            artist_responses = self.api.get_items(
                artist_uris, kind=RemoteObjectType.ARTIST, extend=False, use_cache=self.use_cache
            )

            artists = {response["uri"]: response for response in artist_responses}
            for track in self.tracks:
                track.response["artists"] = [artists[artist["uri"]] for artist in track.response["artists"]]

        for track in self.tracks:
            track.refresh(skip_checks=False)  # tracks are popped from albums so checks should skip by default anyway

        self.logger.debug(f"Enrich {self.api.source} tracks: DONE\n")

    def enrich_saved_albums(self) -> None:
        """Extends the tracks data for currently loaded albums, getting all available tracks data for each album"""
        if not self.albums or all(len(album) == album.track_total for album in self.albums):
            return
        self.logger.debug(f"Enrich {self.api.source} artists: START")
        self.logger.info(
            f"\33[1;95m  >\33[1;97m Enriching {len(self.albums)} {self.api.source} albums \33[0m"
        )

        kind = RemoteObjectType.ALBUM
        key = self.api.collection_item_map[kind]

        for album in self.albums:
            self.api.extend_items(album, kind=kind, key=key, use_cache=self.use_cache)
            album.refresh(skip_checks=False)

            for track in album.tracks:  # add tracks from this album to the user's saved tracks
                if track not in self.tracks:
                    self._tracks.append(track)

        self.logger.debug(f"Enrich {self.api.source} artists: DONE\n")

    def enrich_saved_artists(self, tracks: bool = False, types: Collection[str] = ()) -> None:
        """
        Gets all albums for current loaded following artists.

        :param tracks: When True, also get all tracks for each album.
        :param types: Provide a list of albums types to get to limit the types of albums loaded.
            Select from ``{"album", "single", "compilation", "appears_on"}``.
        """
        if not self.artists:
            return
        self.logger.debug(f"Enrich {self.api.source} artists: START")
        self.logger.info(
            f"\33[1;95m  >\33[1;97m Enriching {len(self.artists)} {self.api.source} artists \33[0m"
        )

        self.api.get_artist_albums(self.artists, types=types, use_cache=self.use_cache)

        if tracks:
            kind = RemoteObjectType.ALBUM
            key = self.api.collection_item_map[kind]

            responses_albums = [album for artist in self.artists for album in artist.albums]
            bar = self.logger.get_progress_bar(iterable=responses_albums, desc="Getting album tracks", unit="albums")
            for album in bar:
                self.api.extend_items(album, kind=kind, key=key, use_cache=self.use_cache)
                album.refresh(skip_checks=False)

        self.logger.debug(f"Enrich {self.api.source} artists: DONE\n")

    def merge_playlists(
            self,
            playlists: Library[RemoteTrack] | Collection[Playlist[RemoteTrack]] | Mapping[Any, Playlist[RemoteTrack]]
    ) -> None:
        raise NotImplementedError
