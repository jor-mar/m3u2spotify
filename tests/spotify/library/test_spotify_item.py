from copy import deepcopy
from typing import Any

import pytest

from syncify.api.exception import APIError
from syncify.remote.exception import RemoteObjectTypeError
from syncify.spotify.api import SpotifyAPI
from syncify.spotify.library.item import SpotifyTrack, SpotifyArtist
from tests.abstract.item import ItemTester
from tests.spotify.api.mock import SpotifyMock
from tests.spotify.library.utils import assert_id_attributes


class TestSpotifyArtist(ItemTester):

    @pytest.fixture
    def item(self, response_random: dict[str, Any]) -> SpotifyArtist:
        return SpotifyArtist(response_random)

    @pytest.fixture
    def item_unequal(self, response_valid: dict[str, Any]) -> SpotifyArtist:
        return SpotifyArtist(response_valid)

    @pytest.fixture
    def item_modified(self, response_random: dict[str, Any]) -> SpotifyArtist:
        artist = SpotifyArtist(response_random)
        artist.response["name"] = "new name"
        artist.response["genres"] = ["electronic", "dance"]
        artist.response["popularity"] = 200
        return artist

    @pytest.fixture
    def response_random(self) -> dict[str, Any]:
        """Yield a randomly generated response from the Spotify API for an artist item type"""
        return SpotifyMock.generate_artist()

    @pytest.fixture
    def response_valid(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a valid enriched response from the Spotify API for an artist item type."""
        return deepcopy(next(artist for artist in api_mock.artists if artist["genres"]))

    def test_input_validation(self, response_random: dict[str, Any], api_mock: SpotifyMock):
        with pytest.raises(RemoteObjectTypeError):
            SpotifyArtist(api_mock.generate_track(artists=False, album=False))

        SpotifyArtist.api = None
        with pytest.raises(APIError):
            SpotifyArtist.load(api_mock.artists[0]["href"])
        with pytest.raises(APIError):
            SpotifyArtist(response_random).reload()

    def test_attributes(self, response_random: dict[str, Any]):
        artist = SpotifyArtist(response_random)
        original_response = deepcopy(response_random)

        assert_id_attributes(item=artist, response=original_response)

        assert artist.name == artist.artist
        assert artist.artist == original_response["name"]
        new_name = "new name"
        artist.response["name"] = new_name
        assert artist.artist == new_name

        assert artist.genres == original_response["genres"]
        new_genres = ["electronic", "dance"]
        artist.response["genres"] = new_genres
        assert artist.genres == new_genres

        if not artist.has_image:
            artist.response["images"] = [{"height": 200, "url": "old url"}]
        images = {image["height"]: image["url"] for image in artist.response["images"]}
        assert len(artist.image_links) == 1
        assert artist.image_links["cover_front"] == next(url for height, url in images.items() if height == max(images))
        new_image_link = "new url"
        artist.response["images"].append({"height": max(images) * 2, "url": new_image_link})
        assert artist.image_links["cover_front"] == new_image_link

        assert artist.rating == original_response["popularity"]
        new_rating = artist.rating + 20
        artist.response["popularity"] = new_rating
        assert artist.rating == new_rating

        assert artist.followers == original_response["followers"]["total"]
        new_followers = artist.followers + 20
        artist.response["followers"]["total"] = new_followers
        assert artist.followers == new_followers

    def test_reload(self, response_valid: dict[str, Any], api: SpotifyAPI):
        response_valid.pop("genres", None)
        response_valid.pop("popularity", None)
        response_valid.pop("followers", None)

        artist = SpotifyArtist(response_valid)
        assert not artist.genres
        assert artist.rating is None
        assert artist.followers is None

        SpotifyArtist.api = api
        artist.reload()
        assert artist.genres
        assert artist.rating is not None
        assert artist.followers is not None

    def test_load(self, response_valid: dict[str, Any], api: SpotifyAPI):
        SpotifyArtist.api = api
        artist = SpotifyArtist.load(response_valid["href"])

        assert artist.name == response_valid["name"]
        assert artist.id == response_valid["id"]
        assert artist.url == response_valid["href"]


class TestSpotifyTrack(ItemTester):

    @pytest.fixture
    def item(self, response_random: dict[str, Any]) -> SpotifyTrack:
        return SpotifyTrack(response_random)

    @pytest.fixture
    def item_unequal(self, response_valid: dict[str, Any]) -> SpotifyTrack:
        return SpotifyTrack(response_valid)

    @pytest.fixture
    def item_modified(self, response_random: dict[str, Any]) -> SpotifyTrack:
        track = SpotifyTrack(response_random)
        track.response["name"] = "new name"
        track.response["artists"] = [{"name": artist} for artist in ["artist 1", "artist 2"]]
        track.response["track_number"] = 500
        track.response["popularity"] = 200
        return track

    @pytest.fixture
    def response_random(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """Yield a randomly generated response from the Spotify API for a track item type"""
        return api_mock.generate_track()

    @pytest.fixture
    def response_valid(self, api_mock: SpotifyMock) -> dict[str, Any]:
        """
        Yield a valid enriched response with extended artists and albums responses
        from the Spotify API for a track item type.
        """
        return deepcopy(next(track for track in api_mock.tracks))

    def test_input_validation(self, response_random: dict[str, Any], api_mock: SpotifyMock):
        with pytest.raises(RemoteObjectTypeError):
            SpotifyTrack(api_mock.generate_artist(properties=False))

        SpotifyTrack.api = None
        with pytest.raises(APIError):
            SpotifyTrack.load(api_mock.tracks[0]["href"])
        with pytest.raises(APIError):
            SpotifyTrack(response_random).reload()

    def test_attributes(self, response_random: dict[str, Any]):
        track = SpotifyTrack(response_random)
        original_response = deepcopy(response_random)

        assert_id_attributes(item=track, response=original_response)

        assert track.name == track.title
        assert track.title == original_response["name"]
        new_name = "new name"
        track.response["name"] = new_name
        assert track.title == new_name

        original_artists = [artist["name"] for artist in original_response["artists"]]
        assert track.artist == track.tag_sep.join(original_artists)
        assert len(track.artists) == len(original_artists)
        new_artists = ["artist 1", "artist 2"]
        track.response["artists"] = [{"name": artist} for artist in new_artists]
        assert track.artist == track.tag_sep.join(new_artists)

        assert track.album == original_response["album"]["name"]
        new_album = "new album"
        track.response["album"]["name"] = new_album
        assert track.album == new_album

        original_album_artists = [artist["name"] for artist in original_response["album"]["artists"]]
        original_album_artist = track.tag_sep.join(original_album_artists)
        assert track.album_artist == original_album_artist
        new_album_artists = ["album artist 1", "album artist 2"]
        track.response["album"]["artists"] = [{"name": artist} for artist in new_album_artists]
        assert track.album_artist == track.tag_sep.join(new_album_artists)

        assert track.track_number == original_response["track_number"]
        new_track_number = track.track_number + 4
        track.response["track_number"] = new_track_number
        assert track.track_number == new_track_number

        assert track.track_total == original_response["album"]["total_tracks"]
        new_track_total = track.track_total + 20
        track.response["album"]["total_tracks"] = new_track_total
        assert track.track_total == new_track_total

        assert not original_response["album"].get("genres")
        assert not original_response["artists"][0].get("genres")
        assert not track.genres
        new_genres_artist = ["electronic", "dance"]
        track.response["artists"][0]["genres"] = new_genres_artist
        assert track.genres == [g.title() for g in new_genres_artist]
        new_genres_album = ["rock", "jazz", "pop rock"]
        track.response["album"]["genres"] = new_genres_album
        assert track.genres == [g.title() for g in new_genres_album]

        assert track.year == int(original_response["album"]["release_date"][:4])
        new_year = track.year + 20
        track.response["album"]["release_date"] = f"{new_year}-12-01"
        assert track.year == new_year

        assert "audio_features" not in track.response
        assert not track.bpm
        new_bpm = 120.123
        track.response["audio_features"] = {"tempo": 120.123}
        assert track.bpm == new_bpm
        track.response.pop("audio_features")

        assert not track.key
        new_key = 4
        track.response["audio_features"] = {"key": new_key, "mode": 1}
        assert track.key == track._song_keys[new_key]
        track.response["audio_features"]["mode"] = 0
        assert track.key == track._song_keys[new_key] + "m"
        track.response["audio_features"] = {"key": -1, "mode": 0}
        assert not track.key

        assert not track.disc_total
        assert track.disc_number == original_response["disc_number"]
        new_disc_number = track.disc_number + 5
        track.response["disc_number"] = new_disc_number
        assert track.disc_number == new_disc_number

        track.response["album"]["album_type"] = "compilation"
        assert track.compilation
        track.response["album"]["album_type"] = "album"
        assert not track.compilation

        if not track.has_image:
            track.response["album"]["images"] = [{"height": 200, "url": "old url"}]
        images = {image["height"]: image["url"] for image in track.response["album"]["images"]}
        assert len(track.image_links) == 1
        assert track.image_links["cover_front"] == next(url for height, url in images.items() if height == max(images))
        new_image_link = "new url"
        track.response["album"]["images"].append({"height": max(images) * 2, "url": new_image_link})
        assert track.image_links["cover_front"] == new_image_link

        assert track.length == original_response["duration_ms"] / 1000
        new_duration = track.response["duration_ms"] + 2000
        track.response["duration_ms"] = new_duration
        assert track.length == new_duration / 1000

        assert track.rating == original_response["popularity"]
        new_rating = track.rating + 20
        track.response["popularity"] = new_rating
        assert track.rating == new_rating

    def test_reload(self, response_valid: dict[str, Any], api: SpotifyAPI):
        response_valid["album"].pop("name", None)
        response_valid.pop("audio_features", None)

        track = SpotifyTrack(response_valid)
        assert not track.album
        assert not track.key
        assert not track.bpm

        SpotifyTrack.api = api
        track.reload()
        assert track.album
        if track.response["audio_features"]["key"] > -1:
            assert track.key
        else:
            assert track.key is None
        assert track.bpm

    def test_load(self, response_valid: dict[str, Any], api: SpotifyAPI):
        SpotifyTrack.api = api
        track = SpotifyTrack.load(response_valid["href"])

        assert track.name == response_valid["name"]
        assert track.id == response_valid["id"]
        assert track.url == response_valid["href"]
