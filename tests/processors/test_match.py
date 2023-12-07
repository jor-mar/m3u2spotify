from syncify.processors.match import ItemMatcher, CleanTagConfig
from tests.abstract.misc import pretty_printer_tests
from tests.local.track import random_track


def get_matcher() -> ItemMatcher:
    """Return an :py:class:`ItemMatcher` object with expected config for subsequent tests."""
    matcher = ItemMatcher()

    matcher.karaoke_tags = {"karaoke", "backing", "instrumental"}
    matcher.year_range = 10

    matcher.clean_tags_remove_all = {"the", "a", "&", "and"}
    matcher.clean_tags_split_all = set()
    matcher.clean_tags_config = (
        CleanTagConfig(name="title", _remove={"part"}, _split={"featuring", "feat.", "ft.", "/"}),
        CleanTagConfig(name="artist", _split={"featuring", "feat.", "ft.", "vs"}),
        CleanTagConfig(name="album", _remove={"ep"}, _preprocess=lambda x: x.split('-')[0])
    )

    matcher.reduce_name_score_on = {"live", "demo", "acoustic"}
    matcher.reduce_name_score_factor = 0.5

    return matcher


# noinspection SpellCheckingInspection
def test_init_and_clean_tags():
    matcher = get_matcher()
    pretty_printer_tests(matcher)

    track = random_track()
    track.uri = "spotify:track:ASDFGHJKLQWERTYUIOPZX"

    track.title = "A Song Part 2"
    track.artist = "Artist 1 & Artist two Feat. Artist 3"
    track.album = "The Best EP - the new one"

    matcher.clean_tags(track)
    assert track.clean_tags["title"] == "song 2"
    assert track.clean_tags["artist"] == "artist 1 artist two"
    assert track.clean_tags["album"] == "best"


def test_match_not_karaoke():
    matcher = get_matcher()

    track = random_track()
    track.title = "title"
    track.artist = "artist"
    track.album = "album"

    assert matcher.match_not_karaoke(track, track) == 1

    track.title = "title backing"
    assert matcher.match_not_karaoke(track, track) == 0

    track.title = "title"
    track.album = "album instrumental"
    assert matcher.match_not_karaoke(track, track) == 0


def test_match_name():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    matcher.clean_tags(track1)
    matcher.clean_tags(track2)

    # no names in at least one item always returns 0
    track1.clean_tags["name"] = None
    track2.clean_tags["name"] = None
    assert matcher.match_name(track1, track2) == 0

    # 1/1 word match
    track1.title = "title"
    track1.clean_tags["name"] = track1.title
    track2.title = "other title"
    track2.clean_tags["name"] = track2.title
    assert matcher.match_name(track1, track2) == 1

    # 0/4 words match
    track1.title = "title of a track"
    track1.clean_tags["name"] = track1.title
    track2.title = "song"
    track2.clean_tags["name"] = track2.title
    assert matcher.match_name(track1, track2) == 0

    # 2/3 words match
    track1.title = "a longer title"
    track1.clean_tags["name"] = track1.title
    track2.title = "this is a different title"
    track2.clean_tags["name"] = track2.title
    assert round(matcher.match_name(track1, track2), 2) == 0.67


def test_match_artist():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    sep = track1.tag_sep

    # no artists in at least one item always returns 0
    track1.clean_tags["artist"] = "artist"
    track2.clean_tags["artist"] = None
    assert matcher.match_artist(track1, track2) == 0

    # 1/4 words match
    track1.clean_tags["artist"] = f"band{sep}a singer{sep}artist"
    track2.clean_tags["artist"] = f"artist{sep}nope{sep}other"
    assert matcher.match_artist(track1, track2) == 0.25

    # 2/4 words match, but now weighted
    # match 'artist' = 0.25 + match 'singer' = 0.125
    track1.clean_tags["artist"] = f"band{sep}a singer{sep}artist"
    track2.clean_tags["artist"] = f"artist{sep}singer{sep}other"
    assert matcher.match_artist(track1, track2) == 0.375


def test_match_album():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    matcher.clean_tags(track1)
    matcher.clean_tags(track2)

    # no albums in at least one item always returns 0
    track1.clean_tags["album"] = None
    track2.clean_tags["album"] = "album"
    assert matcher.match_album(track1, track2) == 0

    # 1/2 words match
    track1.clean_tags["album"] = "album name"
    track2.clean_tags["album"] = "name"
    assert matcher.match_album(track1, track2) == 0.5

    # 3/3 words match
    track1.clean_tags["album"] = "brand new album"
    track2.clean_tags["album"] = "this is a brand new really cool album"
    assert matcher.match_album(track1, track2) == 1


def test_match_length():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    matcher.clean_tags(track1)
    matcher.clean_tags(track2)

    # no lengths for at least one item always returns 0
    track1.clean_tags["length"] = 110.20
    track2.clean_tags["length"] = None
    assert matcher.match_length(track1, track2) == 0

    track1.clean_tags["length"] = 100
    track2.clean_tags["length"] = 90
    assert matcher.match_length(track1, track2) == 0.9


def test_match_year():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    matcher.clean_tags(track1)
    matcher.clean_tags(track2)

    # no year for at least one item always returns 0
    track1.clean_tags["year"] = 2023
    track2.clean_tags["year"] = None
    assert matcher.match_year(track1, track2) == 0

    track1.clean_tags["year"] = 2020
    track2.clean_tags["year"] = 2015
    assert matcher.match_year(track1, track2) == 0.5

    track1.clean_tags["year"] = 2020
    track2.clean_tags["year"] = 2010
    assert matcher.match_year(track1, track2) == 0

    track1.clean_tags["year"] = 2020
    track2.clean_tags["year"] = 2005
    assert matcher.match_year(track1, track2) == 0


def test_match_score():
    matcher = get_matcher()

    track1 = random_track()
    track2 = random_track()
    sep = track1.tag_sep

    track1.title = "a longer title"
    track2.title = "this is a different title"
    track1.artist = f"band{sep}a singer{sep}artist"
    track2.artist = f"nope"
    track1.album = "album"
    track2.album = "name"
    track1.file.info.length = 100
    track2.file.info.length = 10
    track1.year = 2020
    track2.year = 2010

    # track2 score is below min_score
    assert matcher.score_match(track1, [track2], min_score=0.2, max_score=0.8) is None

    # track3 score is above min_score
    track3 = random_track()
    track3.title = "this is a different title"
    track3.artist = f"artist{sep}nope{sep}other"
    track3.year = 2015
    assert matcher.score_match(track1, [track2, track3], min_score=0.2, max_score=0.8) == track3

    # track4 score is above max_score causing an early stop
    track4 = random_track()
    track4.title = "a longer title"
    track4.artist = f"band{sep}a singer{sep}artist"
    track4.album = "album"
    track4.file.info.length = 100
    track4.year = 2015
    assert matcher.score_match(track1, [track2, track4, track3], min_score=0.2, max_score=0.8) == track4
