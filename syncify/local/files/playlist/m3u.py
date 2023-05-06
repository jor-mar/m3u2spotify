from dataclasses import dataclass
from os.path import exists
from typing import Optional, List, Set, Collection, Union

from syncify.local.files.track import LocalTrack, load_track, TrackMatch
from syncify.local.files.playlist.playlist import Playlist
from syncify.utils_new.generic import UpdateResult


@dataclass
class UpdateResultM3U(UpdateResult):
    start: int
    added: int
    removed: int
    unchanged: int
    difference: int
    final: int


class M3U(Playlist):
    """
    For reading and writing data from M3U playlist format.
    You must provide either a valid playlist path of a file that exists,
    or a list of tracks to use as this playlist's tracks.
    You may also provide both to use and store the loaded tracks to this instance.

    :param path: Full path of the playlist.
        If the playlist ``path`` given does not exist, the playlist instance will use all the tracks
        given in ``tracks`` as the tracks in the playlist.
    :param tracks: Optional. Available Tracks to search through for matches.
        If no tracks are given, the playlist instance load all the tracks from paths
        listed in file at the playlist ``path``.
    :param library_folder: Full path of folder containing tracks.
    :param other_folders: Full paths of other possible library paths.
        Use to replace path stems from other libraries for the paths in loaded playlists.
        Useful when managing similar libraries on multiple platforms.
    """

    valid_extensions = [".m3u"]

    def __init__(
            self,
            path: str,
            tracks: Optional[List[LocalTrack]] = None,
            library_folder: Optional[str] = None,
            other_folders: Optional[Union[str, Collection[str]]] = None
    ):
        self._validate_type(path)

        paths = []
        if exists(path):
            with open(path, "r", encoding='utf-8') as f:
                paths = [line.strip() for line in f]
        elif tracks is not None:
            paths = [track.path for track in tracks]

        matcher = TrackMatch(include_paths=paths, library_folder=library_folder, other_folders=other_folders)
        Playlist.__init__(self, path=path, matcher=matcher)

        self.load(tracks=tracks)

    def load(self, tracks: Optional[List[LocalTrack]] = None) -> List[LocalTrack]:
        if self.matcher.include_paths is None or len(self.matcher.include_paths) == 0:
            self.tracks = tracks if tracks else []
        elif tracks is not None:
            self._match(tracks)
        else:
            self.tracks = [load_track(path=path) for path in self.matcher.include_paths if path is not None]

        self._limit(ignore=self.matcher.include_paths)
        self._sort()

        return self.tracks

    def save(self) -> UpdateResultM3U:
        start_paths: Set[str] = set()
        if exists(self.path):
            with open(self.path, "r", encoding='utf-8') as f:
                start_paths = {line.rstrip().lower() for line in f if line.rstrip()}
                start_paths = {self.matcher.correct_path_separater(path) for path in start_paths if path}

        with open(self.path, "w", encoding='utf-8') as f:
            paths = self._prepare_paths_for_output([track.path for track in self.tracks])
            f.writelines([path.strip() + '\n' for path in paths])

        with open(self.path, "r", encoding='utf-8') as f:
            final_paths = {line.rstrip().lower() for line in f if line.rstrip()}

        print("PATHS")
        print(start_paths)
        print(final_paths)

        return UpdateResultM3U(
            start=len(start_paths),
            added=len(final_paths - start_paths),
            removed=len(start_paths - final_paths),
            unchanged=len(start_paths.intersection(final_paths)),
            difference=len(final_paths) - len(start_paths),
            final=len(final_paths),
        )
