import pytest

from inventree_ptouch.tape import TAPES, UnsupportedTape, tape_for_width


def test_tape_table():
    assert [(w, t.left_pins, t.band_dots) for w, t in sorted(TAPES.items())] == [
        (4, 52, 24), (6, 48, 32), (9, 39, 50), (12, 29, 70), (18, 8, 112), (24, 0, 128)]
    for t in TAPES.values():
        assert 2 * t.left_pins + t.band_dots == 128


def test_max_length():
    assert TAPES[4].max_length_mm == TAPES[9].max_length_mm == TAPES[12].max_length_mm == 50
    assert TAPES[18].max_length_mm == 80
    assert round(TAPES[24].max_length_mm, 2) == 91.43


def test_band_mm_maps_to_whole_dots():
    assert round(TAPES[12].band_mm / 25.4 * 180) == 70


def test_unknown_width_raises():
    with pytest.raises(UnsupportedTape):
        tape_for_width(36)
    with pytest.raises(UnsupportedTape):
        tape_for_width(0)


def test_tape_for_width_returns_table_entry():
    assert tape_for_width(12) is TAPES[12]
