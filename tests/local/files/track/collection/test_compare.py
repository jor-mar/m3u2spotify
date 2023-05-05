from datetime import datetime, date, timedelta

import pytest

from syncify.local.files.track import TrackCompare, PropertyName, TagName, MP3, M4A, FLAC
from tests.local.files.track.track import random_track


def test_init():
    comparator = TrackCompare(field=TagName.IMAGES, condition="Contains")
    assert comparator.field == TagName.IMAGES
    assert comparator._expected is None
    assert not comparator._converted
    assert comparator._condition == "Contains"
    assert comparator._method == comparator._cond_contains

    comparator = TrackCompare(field=PropertyName.DATE_ADDED, condition="___greater than_  ")
    assert comparator.field == PropertyName.DATE_ADDED
    assert not comparator._converted
    assert comparator._expected is None
    assert comparator._condition == "GreaterThan"
    assert comparator._method == comparator._cond_is_after

    comparator = TrackCompare(field=PropertyName.EXT, condition=" is  _", expected=[".mp3", ".flac"])
    assert comparator.field == PropertyName.EXT
    assert not comparator._converted
    assert comparator._expected == [".mp3", ".flac"]
    assert comparator._condition == "Is"
    assert comparator._method == comparator._cond_is

    with pytest.raises(ValueError):
        assert TrackCompare(field=PropertyName.EXT, condition="this cond does not exist")


def test_compare_with_reference():
    track_1 = random_track()
    track_2 = random_track()

    comparator = TrackCompare(field=TagName.ALBUM, condition="StartsWith")
    assert comparator._expected is None
    assert not comparator._converted

    track_1.album = "album 124 is a great album"
    track_2.album = "album"
    assert comparator.compare(track=track_1, reference=track_2)
    assert comparator._expected is None
    assert not comparator._converted

    with pytest.raises(ValueError):
        assert comparator.compare(track_1)


def test_compare_str():
    track = random_track(MP3)

    # no expected values conversion
    comparator = TrackCompare(field=PropertyName.EXT, condition=" is  _", expected=[".mp3", ".flac"])
    assert comparator._expected == [".mp3", ".flac"]
    assert comparator._method == comparator._cond_is

    assert track.ext == ".mp3"
    assert comparator.compare(track)
    assert comparator._expected == [".mp3", ".flac"]
    assert not comparator.compare(random_track(FLAC))
    assert not comparator.compare(random_track(M4A))


def test_compare_int():
    track = random_track()

    comparator = TrackCompare(field=TagName.TRACK, condition="is in", expected=["1", 2, "3"])
    assert comparator._expected == ["1", 2, "3"]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is_in

    track.track_number = 3
    assert comparator.compare(track)
    assert comparator._expected == [1, 2, 3]
    assert comparator._converted

    track.track_number = 4
    assert not comparator.compare(track)
    assert comparator._expected == [1, 2, 3]
    assert comparator._converted

    # int: conversion when given a time str
    comparator = TrackCompare(field=PropertyName.LENGTH, condition="greater than", expected="1:30,618")
    assert comparator._expected == ["1:30,618"]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is_after

    track.length = 120
    assert comparator.compare(track)
    assert comparator._expected == [90]
    assert comparator._converted
    track.length = 60
    assert not comparator.compare(track)
    assert comparator._expected == [90]
    assert comparator._converted


def test_compare_float():
    track = random_track()

    # float
    comparator = TrackCompare(field=TagName.BPM, condition="in_range", expected=["81.96", 100.23])
    assert comparator._expected == ["81.96", 100.23]
    assert not comparator._converted
    assert comparator._method == comparator._cond_in_range

    track.bpm = 90.0
    assert comparator.compare(track)
    assert comparator._expected == [81.96, 100.23]
    assert comparator._converted

    # does not convert again when giving a value of a different type
    track.bpm = 120
    assert not comparator.compare(track)
    assert comparator._expected == [81.96, 100.23]
    assert comparator._converted


def test_compare_date():
    track = random_track()

    # all datetime comparisons only consider date part
    comparator = TrackCompare(field=PropertyName.DATE_MODIFIED, condition="is", expected=datetime(2023, 4, 21, 19, 20))
    assert comparator._expected == [datetime(2023, 4, 21, 19, 20)]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is

    track.date_modified = datetime(2023, 4, 21, 11, 30, 49, 203)
    assert comparator.compare(track)
    assert comparator._expected == [date(2023, 4, 21)]
    assert comparator._converted

    # converts supported strings
    comparator = TrackCompare(field=PropertyName.DATE_MODIFIED, condition="is_not", expected="20/01/01")
    assert comparator._expected == ["20/01/01"]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is_not

    assert comparator.compare(track)
    assert comparator._expected == [date(2001, 1, 20)]
    assert comparator._converted

    comparator = TrackCompare(field=PropertyName.DATE_MODIFIED, condition="is_not", expected="13/8/2004")
    assert comparator._expected == ["13/8/2004"]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is_not

    assert comparator.compare(track)
    assert comparator._expected == [date(2004, 8, 13)]
    assert comparator._converted

    # converts date ranges
    comparator = TrackCompare(field=PropertyName.DATE_MODIFIED, condition="is_in_the_last", expected="8h")
    assert comparator._expected == ["8h"]
    assert not comparator._converted
    assert comparator._method == comparator._cond_is_after

    track.date_modified = datetime.now() - timedelta(hours=4)
    assert comparator.compare(track)
    # truncate to avoid time lag between assignment and test making the test fail
    exp_truncated = comparator._expected[0].replace(second=0, microsecond=0)
    test_truncated = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=8)
    assert exp_truncated == test_truncated
    assert comparator._converted



