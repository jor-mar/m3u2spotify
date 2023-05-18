import os
import re
import shutil
import traceback
from datetime import datetime as dt
from glob import glob
from os.path import basename, dirname, isdir, join
from time import perf_counter
from typing import List, Optional, Mapping, Any, Callable

from dateutil.relativedelta import relativedelta

from syncify.local.library import LocalLibrary, MusicBee
from syncify.local.track.base.tags import TagName
from syncify.report import Report
from syncify.settings import Settings
from syncify.spotify.api import API
from syncify.spotify.library import SpotifyLibrary
from syncify.spotify.library.response import SpotifyResponse
from syncify.spotify.processor import Searcher, Checker
from syncify.spotify.processor.search import AlgorithmSettings
from syncify.utils.logger import Logger


class Syncify(Settings, Report):
    allowed_functions = ["pause",
                         "clean_up_env",
                         "search",
                         "update_tags",
                         "update_compilations",
                         "update_spotify",
                         "report",
                         ]

    @property
    def time_taken(self) -> float:
        return perf_counter() - self._start_time

    @property
    def api(self) -> API:
        if self._api is None:
            self._api = API(**self.cfg_run["spotify"]["api"]["settings"])
        return self._api

    @property
    def use_cache(self) -> bool:
        return self.cfg_run.get("spotify", {}).get("api", {}).get("use_cache", True)

    @property
    def local_library(self) -> LocalLibrary:
        if self._local_library is None:
            library_folder = self.cfg_run["local"]["paths"].get("library")
            musicbee_folder = self.cfg_run["local"]["paths"].get("musicbee")
            playlist_folder = self.cfg_run["local"]["paths"].get("playlist")
            other_folders = self.cfg_run["local"]["paths"].get("other")
            include = self.cfg_run["local"].get("playlists", {}).get("include")
            exclude = self.cfg_run["local"].get("playlists", {}).get("exclude")

            if musicbee_folder:
                self._local_library = MusicBee(library_folder=library_folder, musicbee_folder=musicbee_folder,
                                               other_folders=other_folders, include=include, exclude=exclude)
            else:
                self._local_library = LocalLibrary(library_folder=library_folder, playlist_folder=playlist_folder,
                                                   other_folders=other_folders, include=include, exclude=exclude)
        return self._local_library

    @property
    def spotify_library(self) -> SpotifyLibrary:
        if self._spotify_library is None:
            use_cache = self.cfg_run["spotify"]["api"].get("use_cache", True)
            include = self.cfg_run["spotify"].get("playlists", {}).get("include")
            exclude = self.cfg_run["spotify"].get("playlists", {}).get("exclude")

            self._spotify_library = SpotifyLibrary(api=self.api, include=include, exclude=exclude, use_cache=use_cache)
        return self._spotify_library

    def __init__(self, config_path: str = "config.yml"):
        self._start_time = perf_counter()  # for measuring total runtime
        Settings.__init__(self, config_path=config_path)
        Logger.__init__(self)

        self.run: Optional[Callable] = None
        self.cfg_run: Mapping[Any, Any] = self.cfg_general

        self._api: Optional[API] = None
        self._local_library: Optional[LocalLibrary] = None
        self._android_library: Optional[LocalLibrary] = None
        self._spotify_library: Optional[SpotifyLibrary] = None

        self.logger.debug(f"Initialisation of Syncify object: DONE\n")

    def set_func(self, name: str):
        self.run = getattr(self, name)
        self.cfg_run = self.cfg_functions.get(name, self.cfg_general)

    def pause(self):
        message = self.cfg_run.get("message", "Pausing, hit return to continue...").strip()
        input(f"\33[93m{message}\33[0m | ")

    def clean_up_env(self) -> None:
        """Clears files older than a number of days and only keeps max # of runs"""
        days = self.cfg_general["cleanup"]["days"]
        runs = self.cfg_general["cleanup"]["runs"]

        logs = dirname(self.log_folder)
        output = dirname(self.output_folder)
        current_logs = [d for d in glob(join(logs, "*")) if isdir(d) and d != self.log_path]
        current_output = [d for d in glob(join(output, "*")) if isdir(d) and d != self.output_folder]

        self.logger.debug(f"Log folders: {len(current_logs)} | Output folders: {len(current_output)} | "
                          f"Days: {days} | Runs: {runs}")

        remove = []
        dates = []

        def get_paths_to_remove(paths: List[str]):
            remaining = len(paths) + 1

            for path in sorted(paths):
                folder = basename(path)
                if not re.match(r"\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}.*", folder):
                    continue
                folder_dt = dt.strptime(folder[:19], self.dt_format)
                dt_diff = folder_dt < dt.now() - relativedelta(days=days)

                # empty folder or too many or too old or date set to be removed
                if not os.listdir(path) or remaining >= runs or dt_diff or folder_dt in dates:
                    remove.append(path)
                    dates.append(folder_dt)
                    remaining -= 1

        get_paths_to_remove(current_output)
        get_paths_to_remove(current_logs)

        for p in remove:
            self.logger.debug(f"Removing {p}")
            shutil.rmtree(p)

    ###########################################################################
    ## Backup/Restore
    ###########################################################################
    def backup(self, **kwargs) -> None:
        """Backup all URI lists for local files/playlists and Spotify playlists"""
        if self._headers is None:
            self._headers = self.auth()

        # backup local library
        self._library_local = self.load_local_metadata(**kwargs)
        library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
        self.enrich_metadata(library_path_metadata)
        self.save_json(self._library_local, "backup__local_library", **kwargs)
        path_uri = self.convert_metadata(self._library_local, key="path", fields="uri", sort_keys=True, **kwargs)
        self.save_json(path_uri, "backup__local_library_URIs", **kwargs)

        # backup playlists and lists of tracks per playlist
        shutil.copytree(self._playlists_path, join(self._data_path, "backup__local_playlists"))
        self._playlists_local = self.get_local_playlists_metadata(tracks=library_path_metadata, **kwargs)
        self.save_json(self._playlists_local, "backup__local_playlists", **kwargs)

        # backup list of tracks per Spotify playlist
        add_extra = self.convert_metadata(self._library_local, key=None, fields=self.extra_spotify_fields, **kwargs)
        add_extra = [track for track in add_extra if isinstance(track['uri'], str)]
        self._playlists_spotify = self.get_playlists_metadata('local', add_extra=add_extra, **kwargs)
        self.save_json(self._playlists_spotify, "backup__spotify_playlists", **kwargs)

    def restore(self, quickload: str, kind: str, mod: str = None, **kwargs) -> None:
        """Restore  URI lists for local files/playlists and Spotify playlists
        
        :param kind: str. Restore 'local' or 'spotify'.
        :param mod: str, default=None. If kind='local', restore 'playlists' from syncify.local or restore playlists from 'spotify'
        """
        if not quickload:
            self.logger.warning("\n\33[91mSet a date to restore from using the quickload arg\33[0m")
            return

        if kind == "local":
            if not mod:  # local URIs
                self._library_local = self.load_local_metadata(**kwargs)
                library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
                self.enrich_metadata(library_path_metadata)
                self.save_json(self._library_local, "01_library__initial", **kwargs)
                self.restore_local_uris(self._library_local, f"{quickload}/backup__local_library_URIs", **kwargs)
            elif mod.lower().startswith("playlist"):
                self.restore_local_playlists(f"{quickload}/backup__local_playlists", **kwargs)
            elif mod.lower().startswith("spotify"):
                self.restore_local_playlists(f"{quickload}/backup__spotify_playlists", **kwargs)
        else:  # spotify playlists
            if self._headers is None:
                self._headers = self.auth()
            self.restore_spotify_playlists(f"{quickload}/backup__spotify_playlists", **kwargs)

    ###########################################################################
    ## Utilities/Misc.
    ###########################################################################
    def missing_tags(self, **kwargs) -> None:
        """Produces report on local tracks with defined set of missing tags"""

        # loads filtered library if filtering given, entire library if not
        self._library_local = self.load_local_metadata(**kwargs)
        library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
        self.enrich_metadata(library_path_metadata)
        self.save_json(self._library_local, "01_library__initial", **kwargs)

        missing_tags = self.report_missing_tags(self._library_local, **kwargs)
        self.save_json(missing_tags, "14_library__missing_tags", **kwargs)

    def extract(self, kind: str, playlists: bool = False, **kwargs):
        """Extract and save images from syncify.local files or Spotify"""

        self._library_local = self.load_local_metadata(**kwargs)
        library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
        self.enrich_metadata(library_path_metadata)

        extract = []
        if kind == 'local':
            if not playlists:  # extract from entire local library
                self.save_json(self._library_local, "01_library__initial", **kwargs)
            else:  # extract from syncify.local playlists
                self._playlists_local = self.get_local_playlists_metadata(tracks=library_path_metadata, **kwargs)
                self.save_json(extract, "10_playlists__local", **kwargs)
        elif kind == 'spotify':
            if self._headers is None:
                self._headers = self.auth()
            if not playlists:  # extract from Spotify for entire library
                extract = self._extract_all_from_spotify(**kwargs)
                local = self.convert_metadata(self._library_local, key="uri", fields="track", **kwargs)

                for tracks in extract.values():
                    for track in tracks:
                        track["position"] = local[track["uri"]]
            else:  # extract from Spotify playlists
                extract = self.get_playlists_metadata('local', **kwargs)
                self.save_json(extract, "11_playlists__spotify_initial", **kwargs)

        self.extract_images(extract, True)

    def sync(self, **kwargs) -> None:
        """Synchrionise local playlists with external"""
        self.clean_playlists()

        self._library_local = self.load_local_metadata(**kwargs)
        library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
        self.enrich_metadata(library_path_metadata)
        self.save_json(self._library_local, "09_library__final", **kwargs)

        self._playlists_local = self.get_local_playlists_metadata(tracks=library_path_metadata, **kwargs)
        self.save_json(self._playlists_local, "10_playlists__local", **kwargs)

        self.compare_playlists(self._playlists_local, **kwargs)

    def check(self, **kwargs) -> None:
        """Run check on entire library and update stored URIs tags"""
        if self._headers is None:
            self._headers = self.auth()

        # loads filtered library if filtering given, entire library if not
        self._library_local = self.load_local_metadata(**kwargs)
        library_path_metadata = self.convert_metadata(self._library_local, key="path", **kwargs)
        self.enrich_metadata(library_path_metadata)
        self.save_json(self._library_local, "01_library__initial", **kwargs)
        path_uri = self.convert_metadata(self._library_local, key="path", fields="uri", sort_keys=True, **kwargs)
        self.save_json(path_uri, "URIs_initial", **kwargs)

        self.check_tracks(self._library_local, report_file="04_report__updated_uris", **kwargs)
        self.save_json(self._library_local, "05_report__check_matches", **kwargs)
        self.save_json(self._library_local, "06_library__checked", **kwargs)

        kwargs['tags'] = ['uri']
        self.update_file_tags(self._library_local, **kwargs)

        # create backup of new URIs
        path_uri = self.convert_metadata(self._library_local, key="path", fields="uri", sort_keys=True, **kwargs)
        self.save_json(path_uri, "URIs", **kwargs)
        self.save_json(path_uri, "URIs", parent=True, **kwargs)

    ###########################################################################
    ## Main runtime functions
    ###########################################################################
    def search(self) -> None:
        """Run all methods for searching, checking, and saving URI associations for local files."""
        albums = self.local_library.albums
        [album.items.remove(track) for album in albums for track in album.items.copy() if track.has_uri is not None]
        [albums.remove(album) for album in albums.copy() if len(album.items) == 0]

        if len(albums) == 0:
            self.logger.info("\33[1;95m ->\33[0;96m All items matched or unavailable. Skipping search.\33[0m")
            return

        cfg = self.cfg_run["spotify"]
        SpotifyResponse.api = self.api

        allow_karaoke = AlgorithmSettings.ITEMS.allow_karaoke
        searcher = Searcher(api=self.api, allow_karaoke=allow_karaoke)
        searcher.search(albums)

        checker = Checker(api=self.api, allow_karaoke=allow_karaoke)
        checker.check(albums, interval=cfg.get("check", {}).get("interval", 10))

    def update_tags(self) -> None:
        """Run all main functions for updating local files"""
        self.logger.debug("Update tags: START")

        replace = self.cfg_run.get("local", {}).get("update", {}).get("replace", False)
        tag_names = self.cfg_run.get("local", {}).get("update", {}).get("tags")
        if not tag_names:
            tags = TagName.ALL
        else:
            tags = [TagName.from_name(tag_name) for tag_name in tag_names]

        # add extra local tracks to Spotify library and merge Spotify data to local library
        self.spotify_library.extend(self.local_library)
        self.local_library.merge(self.spotify_library, tags=tags)

        self.logger.info(f"\33[1;95m ->\33[1;97m Updating tags for {len(self.local_library)} tracks: "
                         f"{', '.join(t.name.lower() for t in tags)} \33[0m")
        results = self.local_library.save_tracks(tags=tags, replace=replace, dry_run=self.dry_run)

        saved = sum(r.saved for r in results.values())
        updated = sum(len(r.updated) > 0 for r in results.values())
        self.logger.info(f"\33[92m    Done | Set tags for {updated} tracks | Saved {saved} tracks \33[0m")
        self.logger.debug("Update tags: DONE\n")

    def update_compilations(self):
        self.logger.debug("Update compilations: START")
        include_prefix = self.cfg_run.get("filter", {}).get("include", {}).get("prefix", "").strip().lower()
        exclude_prefix = self.cfg_run.get("filter", {}).get("exclude", {}).get("prefix", "").strip().lower()
        start = self.cfg_run.get("filter", {}).get("start", "").strip().lower()
        stop = self.cfg_run.get("filter", {}).get("stop", "").strip().lower()

        folders = []
        for folder in self.local_library.folders:
            name = folder.name.strip().lower()
            conditionals = [not include_prefix or name.startswith(include_prefix),
                            not exclude_prefix or not name.startswith(exclude_prefix),
                            not start or name >= start, not stop or name <= stop]
            if all(conditionals):
                folders.append(folder)

        replace = self.cfg_run.get("local", {}).get("update", {}).get("replace", False)
        tag_names = self.cfg_run.get("local", {}).get("update", {}).get("tags")
        if not tag_names:
            tags = TagName.ALL
        else:
            tags = [TagName.from_name(tag_name) for tag_name in tag_names]
        item_count = sum(len(folder) for folder in folders)

        self.logger.info(f"\33[1;95m ->\33[1;97m Setting and saving compilation style tags "
                         f"for {item_count} tracks in {len(folders)} folders: "
                         f"{', '.join(t.name.lower() for t in tags)} \33[0m")

        results = {}
        for folder in folders:
            folder.set_compilation_tags()
            results.update(folder.save_tracks(tags=tags, replace=replace, dry_run=self.dry_run))

        saved = sum(r.saved for r in results.values())
        updated = sum(len(r.updated) > 0 for r in results.values())
        self.logger.info(f"\33[92m    Done | Set tags for {updated} tracks | Saved {saved} tracks \33[0m")
        self.logger.debug("Update compilations: Done\n")

    def update_spotify(self) -> None:
        """Run all main functions for updating Spotify playlists"""
        self.logger.debug("Update Spotify: START")

        if self._local_library is not None:  # reload local library
            self.local_library.load(tracks=False, playlists=True, log=False)

        cfg_playlists = self.cfg_run.get("spotify", {}).get("playlists", {})

        filter_tags = cfg_playlists.get("sync", {}).get("filter", {})
        include = cfg_playlists.get("include", [])
        exclude = cfg_playlists.get("exclude")

        playlists = self.local_library.get_filtered_playlists(**filter_tags)
        playlists = {name: pl for name, pl in playlists.items()
                     if (not include or name in include) and (not exclude or name not in exclude)}

        clear = cfg_playlists.get("sync", {}).get("clear")
        reload = cfg_playlists.get("sync", {}).get("reload")
        self.spotify_library.sync(playlists, clear=clear, reload=reload)
        self.logger.debug("Update Spotify: DONE\n")

    def report(self) -> None:
        if self._local_library is not None:  # reload local library
            self.local_library.load(tracks=True, playlists=True, log=False)
        if self._spotify_library is not None:  # reload Spotify library
            self.spotify_library.use_cache = self.use_cache
            self.spotify_library.load(log=False)

        self.report_library_differences(self.local_library, self.spotify_library)
        self.report_missing_tags(self.local_library.folders)


if __name__ == "__main__":
    main = Syncify()
    # env.get_kwargs()
    main.parse_from_prompt()

    for func in main.functions:
        try:  # run the functions requested by the user
            main.set_func(func)
            main.logger.info(f"\33[95mBegin running \33[1;95m{func}\33[0;95m function \33[0m")
            main.logger.info(f"\33[90mLogs: {main.log_path} \33[0m")
            main.logger.info(f"\33[90mOutput: {main.output_folder} \33[0m")
            main.print_line()
            main.run()
            # main._close_handlers()
        except BaseException:
            main.logger.critical(traceback.format_exc())
            break

        main.print_line()
        main.logger.info(f"\33[95m\33[1;95m{func}\33[0;95m complete\33[0m")
        main.logger.info(f"\33[90mLogs: {main.log_path} \33[0m")
        main.logger.info(f"\33[90mOutput: {main.output_folder} \33[0m")
        print(f"\33[96;1m{'-' * 80}\33[0m")

    print()
    seconds = main.time_taken
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    main.logger.info(f"\33[95mSyncified in {mins} mins {secs} secs \33[0m")

# TODO: track audio recognition when searching using Shazam like service?
# TODO: Automatically add songs added to each Spotify playlist to '2get'?
#  Then somehow update local library playlists after...
#  Maybe add a final step that syncs Spotify back to library if
#  uris for extra songs in Spotify playlists found in library
# TODO: function to open search website tabs for all songs in 2get playlist
#  on common music stores/torrent sites
# TODO: get_items returns 100 items and it's messing up the items extension parts of input responses?
