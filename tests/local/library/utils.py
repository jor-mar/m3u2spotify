from abc import ABCMeta, abstractmethod
from os.path import splitext, basename, join, dirname

from syncify.local.library import LocalLibrary
from tests.abstract.collection import LibraryTester
from tests.local.playlist.utils import path_playlist_resources, path_playlist_m3u
from tests.local.playlist.utils import path_playlist_xautopf_bp, path_playlist_xautopf_ra
from tests.local.test_local_collection import LocalCollectionTester
from tests.local.utils import path_track_resources, path_track_all
from tests.utils import path_resources

path_library_resources = join(path_resources, basename(dirname(__file__)))


class LocalLibraryTester(LibraryTester, LocalCollectionTester, metaclass=ABCMeta):

    dict_json_equal = False

    @abstractmethod
    def blank_library(self) -> LocalLibrary:
        """A blank :py:class:`LocalLibrary` implementation to be tested."""
        raise NotImplementedError

    @staticmethod
    def test_blank_library(blank_library: LocalLibrary) -> None:
        """General tests to run for every implementation of :py:class:`LocalLibrary`"""

        assert blank_library.library_folder is None
        assert len(blank_library._track_paths) == 0
        blank_library.library_folder = path_track_resources
        assert blank_library.library_folder == path_track_resources
        assert blank_library._track_paths == path_track_all

        assert blank_library.playlist_folder is None
        assert blank_library._playlist_paths is None
        blank_library.playlist_folder = path_playlist_resources
        assert blank_library.playlist_folder == path_playlist_resources
        assert blank_library._playlist_paths == {
            splitext(basename(path_playlist_m3u).casefold())[0]: path_playlist_m3u,
            splitext(basename(path_playlist_xautopf_bp).casefold())[0]: path_playlist_xautopf_bp,
            splitext(basename(path_playlist_xautopf_ra).casefold())[0]: path_playlist_xautopf_ra,
        }

    def test_merge_playlists(self, library: LocalLibrary):
        # TODO: write merge_playlists tests
        pass
