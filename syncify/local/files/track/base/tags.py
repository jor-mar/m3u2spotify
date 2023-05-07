from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional, List, Mapping, Set, Self

from syncify.utils_new.exception import EnumNotFoundError


@dataclass
class TagMap:
    """Map of human-friendly tag name to ID3 tag ids for a given file type"""

    title: List[str]
    artist: List[str]
    album: List[str]
    album_artist: List[str]
    track_number: List[str]
    track_total: List[str]
    genres: List[str]
    year: List[str]
    bpm: List[str]
    key: List[str]
    disc_number: List[str]
    disc_total: List[str]
    compilation: List[str]
    comments: List[str]
    images: List[str]


@dataclass
class Tags:
    """Tags that can be extracted for a given track and their related inferred attributes"""
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    album_artist: Optional[str]
    track_number: Optional[int]
    track_total: Optional[int]
    genres: Optional[List[str]]
    year: Optional[int]
    bpm: Optional[float]
    key: Optional[str]
    disc_number: Optional[int]
    disc_total: Optional[int]
    compilation: Optional[bool]
    comments: Optional[List[str]]

    uri: Optional[str]
    has_uri: Optional[bool]

    image_links: Optional[Mapping[str, str]]
    has_image: bool


@dataclass
class Properties:
    """Properties that can be extracted from a file"""
    # file properties
    path: Optional[str]
    folder: Optional[str]
    filename: Optional[str]
    ext: Optional[str]
    size: Optional[int]
    length: Optional[float]
    date_modified: Optional[datetime]

    # library properties
    date_added: Optional[datetime]
    last_played: Optional[datetime]
    play_count: Optional[int]
    rating: Optional[int]


class Name(IntEnum):

    @classmethod
    def all(cls) -> Set[Self]:
        return {e for e in cls if e.name != "ALL"}

    @classmethod
    def from_name(cls, name: str) -> Self:
        """
        Returns the first enum that matches the given name

        :exception EnumNotFoundError: If a corresponding enum cannot be found.
        """
        for enum in cls:
            if enum.name.startswith(name.split("_")[0].upper()):
                return enum
        raise EnumNotFoundError(name)

    @classmethod
    def from_value(cls, value: int) -> Self:
        """
        Returns the first enum that matches the given enum value

        :exception EnumNotFoundError: If a corresponding enum cannot be found.
        """
        for enum in cls:
            if enum.value == value:
                return enum
        raise EnumNotFoundError(value)


class TagName(Name):
    """
    Human-friendly enum tag names using condensed names
    e.g. ``track_number`` and ``track_total`` are condensed to just ``track`` here
    """

    ALL = 0
    TITLE = 65
    ARTIST = 32
    ALBUM = 30  # MusicBee album ignoring articles like 'the' and 'a' etc.
    ALBUM_ARTIST = 31
    TRACK = 86
    GENRES = 59
    YEAR = 35
    BPM = 85
    KEY = 900  # unknown MusicBee mapping
    DISC = 3
    COMPILATION = 901  # unknown MusicBee mapping
    COMMENTS = 44
    URI = 902  # no MusicBee mapping
    IMAGES = 903  # unknown MusicBee mapping

    @classmethod
    def to_tag(cls, enum: Self) -> List[str]:
        """
        Returns all human-friendly tag names for a given enum
        e.g. ``track`` returns both ``track_number`` and ``track_total`` tag names
        """
        return [tag for tag in TagMap.__annotations__ if tag.startswith(enum.name.lower())]


class PropertyName(Name):
    """Enums for properties that can be extracted from a file"""

    ALL = 0

    # file properties
    PATH = 106
    FOLDER = 179
    FILENAME = 52
    EXT = 100
    SIZE = 7
    LENGTH = 16
    DATE_MODIFIED = 11

    # library properties
    DATE_ADDED = 12
    LAST_PLAYED = 13
    PLAY_COUNT = 14
    RATING = 75
