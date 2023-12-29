from syncify.remote.config import RemoteObjectClasses
from syncify.remote.processors.check import RemoteItemChecker
from syncify.remote.processors.search import RemoteItemSearcher
from syncify.spotify.library.object import SpotifyTrack, SpotifyAlbum, SpotifyPlaylist
from syncify.spotify.processors.wrangle import SpotifyDataWrangler

SPOTIFY_OBJECT_TYPES = RemoteObjectClasses(
    track=SpotifyTrack, album=SpotifyAlbum, playlist=SpotifyPlaylist
)


class SpotifyProcessor:
    """Generic base class for Spotify processors."""
    @property
    def _remote_types(self) -> RemoteObjectClasses:
        return SPOTIFY_OBJECT_TYPES


class SpotifyItemChecker(SpotifyProcessor, SpotifyDataWrangler, RemoteItemChecker):
    pass


class SpotifyItemSearcher(SpotifyProcessor, SpotifyDataWrangler, RemoteItemSearcher):
    pass
