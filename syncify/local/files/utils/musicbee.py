import sys
import urllib.parse
from datetime import datetime
from os.path import join, normpath
from typing import Any, List, Mapping, Optional

import xmltodict
from tqdm import tqdm

from local.files.track.track import Track
from syncify.local.files.track.tags import Name, PropertyNames, TagNames

library_path_relative = join("MusicBee", "iTunes Music Library.xml")

# Map of MusicBee field name to Tag or Property
field_name_map = {
    "None": None,
    "Title": TagNames.TITLE,
    "ArtistPeople": TagNames.ARTIST,
    "Album": TagNames.ALBUM,  # album ignoring articles like 'the' and 'a' etc.
    "TrackNo": TagNames.TRACK,
    "GenreSplits": TagNames.GENRES,
    "Year": TagNames.YEAR,
    "Tempo": TagNames.BPM,
    "DiscNo": TagNames.DISC,
    "AlbumArtist": TagNames.ALBUM_ARTIST,
    "Comment": TagNames.COMMENTS,
    "FileDuration": PropertyNames.LENGTH,
    "FolderName": PropertyNames.FOLDER,
    "FilePath": PropertyNames.PATH,
    "FileName": PropertyNames.FILENAME,
    "FileExtension": PropertyNames.EXT,
    "FileDateAdded": PropertyNames.DATE_ADDED,
    "FilePlayCount": PropertyNames.PLAY_COUNT,
}


def get_field_from_code(field_code: int) -> Optional[Name]:
    """Get the Tag or Property for a given MusicBee field code"""
    if field_code == 0:
        return
    elif field_code in [e.value for e in TagNames.all()]:
        return TagNames.from_value(field_code)
    elif field_code in [e.value for e in PropertyNames.all()]:
        return PropertyNames.from_value(field_code)
    elif field_code == 78:  # album including articles like 'the' and 'a' etc.
        return TagNames.ALBUM  # album ignoring articles like 'the' and 'a' etc.
    else:
        raise ValueError(f"Field code not recognised: {field_code}")


def xml_ts_to_dt(timestamp_str: str) -> datetime:
    return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")


def enrich_metadata(tracks: List[Track], library_folder: str) -> None:
    library_path = join(library_folder, library_path_relative)
    with open(library_path, "r", encoding='utf-8') as f:
        xml: Mapping[str, Any] = xmltodict.parse(f.read())

    if not xml:
        return

    # progress bar
    entry_bar = tqdm(
        xml['Tracks'].values(),
        desc="Enriching metadata",
        unit="tracks",
        leave=False,
        disable=False,
        file=sys.stdout,
    )

    path_track = {track.path.lower(): track for track in tracks}
    local_prefix = "file://localhost/"

    for entry in entry_bar:
        if not entry["Location"].startswith(local_prefix):
            continue

        path = urllib.parse.unquote(entry["Location"].replace(local_prefix, ""))
        track = path_track.get(normpath(path))
        if track is None:
            continue

        rating = entry.get('Rating')
        if rating is not None:
            rating = int(rating)

        track.date_added = xml_ts_to_dt(entry.get('Date Added'))
        track.last_played = xml_ts_to_dt(entry.get('Play Date UTC'))
        track.play_count = int(entry.get('Play Count', 0))
        track.rating = rating
