import pytest

from conftest import REAL_STATUS, with_bytes
from inventree_ptouch.protocol import Status, job_pages, page_bytes, raster_line
from inventree_ptouch.tape import TAPES


def test_parse_real_status():
    s = Status.parse(REAL_STATUS)
    assert (s.model, s.media_width, s.media_type, s.status_type) == (0x7F, 12, 0x01, 0x00)
    assert s.problems() == []


def test_parse_rejects_iap_frames():
    with pytest.raises(ValueError):
        Status.parse(bytes.fromhex("ff550200ee10") * 6)


def test_parse_rejects_short_packet():
    with pytest.raises(ValueError):
        Status.parse(REAL_STATUS[:31])


def test_problems_decoded():
    p = " ".join(Status.parse(with_bytes(b8=0x01, b9=0x10, b11=0xFF)).problems()).lower()
    assert "no media" in p and "cover open" in p and "incompatible" in p


def test_extended_error_incompatible_media():
    p = " ".join(Status.parse(with_bytes(b7=0x21)).problems()).lower()
    assert "incompatible" in p


def test_no_tape_is_a_problem():
    assert Status.parse(with_bytes(b10=0x00, b11=0x00)).problems()


def test_weak_battery_is_not_a_problem():
    assert Status.parse(with_bytes(b8=0x08)).problems() == []


def test_raster_line_12mm_pin_mapping():
    col = [0] * 70
    col[0] = 1
    col[69] = 1
    line = raster_line(col, TAPES[12])
    assert len(line) == 16
    assert line == bytes([0, 0, 0, 0x04, 0, 0, 0, 0, 0, 0, 0, 0, 0x20, 0, 0, 0])


def test_raster_line_24mm_full():
    assert raster_line([1] * 128, TAPES[24]) == b"\xff" * 16


def test_raster_line_rejects_wrong_height():
    with pytest.raises(ValueError):
        raster_line([0] * 69, TAPES[12])


def test_raster_line_matches_ptouch_rs_formula():
    for t in TAPES.values():
        for r in (0, t.band_dots // 2, t.band_dots - 1):
            col = [0] * t.band_dots
            col[r] = 1
            p = (64 - t.band_dots // 2) + (t.band_dots - 1 - r)
            exp = bytearray(16)
            exp[15 - p // 8] |= 1 << (p % 8)
            assert raster_line(col, t) == bytes(exp)


def n9(page):
    return page[page.index(b"\x1biz") + 11]


def test_page_bytes_exact():
    lines = [bytes(16)] * 34
    b = page_bytes(lines, TAPES[24], position=2)
    head = bytes.fromhex(
        "1b696101" "1b692100" "1b697a" "84" "00" "18" "00" "22000000" "02" "00"
        "1b694d40" "1b694101" "1b694b08" "1b69640e00" "4d00")
    assert b.startswith(head)
    assert b[len(head):len(head) + 19] == b"G\x10\x00" + bytes(16)
    assert b.endswith(b"\x1a") and len(b) == len(head) + 34 * 19 + 1


def test_esc_i_z_matches_brother_example():
    b = page_bytes([bytes(16)] * 682, TAPES[24], position=2)
    assert bytes.fromhex("1b697a" "840018" "00aa0200000200") in b


def test_page_uses_status_width_code_for_3_5mm():
    b = page_bytes([bytes(16)] * 40, TAPES[4], position=2)
    assert b[b.index(b"\x1biz") + 5] == 0x04


def test_page_length_limits():
    with pytest.raises(ValueError):
        page_bytes([bytes(16)] * 33, TAPES[12], 2)
    with pytest.raises(ValueError):
        page_bytes([bytes(16)] * 7088, TAPES[12], 2)


def test_job_page_positions():
    p = [[bytes(16)] * 40]
    assert [n9(x) for x in job_pages(p, TAPES[12])] == [2]
    two = job_pages(p * 2, TAPES[12])
    three = job_pages(p * 3, TAPES[12])
    assert [n9(x) for x in two] == [0, 2]
    assert [n9(x) for x in three] == [0, 1, 2]
    assert [x[-1:] for x in three] == [b"\x0c", b"\x0c", b"\x1a"]
    assert [x[-1:] for x in job_pages(p, TAPES[12])] == [b"\x1a"]


def test_no_auto_cut():
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, auto_cut=False)
    assert b"\x1biM\x00" in b and b"\x1biA\x00" in b


from inventree_ptouch.models import MODELS


def blank_and_ink(n=40):
    lines = [bytes(16)] * n
    lines[0] = bytes([0xFF] * 16)
    return lines


def test_default_model_is_e560bt():
    assert page_bytes([bytes(16)] * 40, TAPES[12], 2) == page_bytes([bytes(16)] * 40, TAPES[12], 2, model=MODELS["PT-E560BT"])


def test_p710bt_has_no_cut_each_and_uses_pages_0_1():
    m = MODELS["PT-P710BT"]
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, model=m)
    assert b"\x1biA" not in b and b"\x1biK\x08" in b and b"\x1bid\x0e\x00" in b
    p = [[bytes(16)] * 40]
    assert [n9(x) for x in job_pages(p, TAPES[12], model=m)] == [0]
    assert [n9(x) for x in job_pages(p * 3, TAPES[12], model=m)] == [0, 1, 1]
    assert [x[-1:] for x in job_pages(p * 3, TAPES[12], model=m)] == [b"\x0c", b"\x0c", b"\x1a"]


def test_d460bt_follows_ptouch_rs_sequence():
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, model=MODELS["PT-D460BT"])
    assert b.startswith(b"\x1bia\x01\x1biz")
    assert b"\x1bid\x01\x00M\x00" in b and b"\x1biM\x40" in b
    assert b"\x1bi!" not in b and b"\x1biA" not in b and b"\x1biK" not in b


def test_e720bt_packbits_without_info():
    b = page_bytes(blank_and_ink(), TAPES[12], 2, model=MODELS["PT-E720BT"])
    assert b.startswith(b"\x1bia\x01\x1biM\x40M\x02")
    assert b"\x1biz" not in b and b"\x1bid" not in b and b"\x1biK" not in b
    body = b[len(b"\x1bia\x01\x1biM\x40M\x02"):-1]
    assert body == b"G\x11\x00\x0f" + bytes([0xFF] * 16) + b"Z" * 39
    assert b.endswith(b"\x1a")


def test_p300bt_matches_ptouch_rs_vector():
    m = MODELS["PT-P300BT"]
    tape = m.tape(12)
    ink = bytearray(16)
    ink[5] = 0x40
    lines = [bytes(16), bytes(ink)] + [bytes(16)] * 32
    b = page_bytes(lines, tape, 0, auto_cut=True, model=m, media_type=0x01, last=True)
    head = (b"\x1bia\x01"
            + bytes.fromhex("1b697a" "c4" "01" "0c" "00") + (34).to_bytes(4, "little") + b"\x00\x00"
            + b"\x1biM\x00" + b"\x1biK\x08" + b"\x1bid\x00\x00" + b"M\x00")
    assert b.startswith(head)
    body = b[len(head):]
    assert body == b"Z" + b"G\x10\x00" + bytes(ink) + b"Z" * 32 + b"\x1a"


def test_p300bt_raster_uses_middle_pins():
    col = [0] * 64
    col[0] = 1
    col[63] = 1
    line = raster_line(col, MODELS["PT-P300BT"].tape(12))
    assert line == bytes([0, 0, 0, 0, 0x80, 0, 0, 0, 0, 0, 0, 0x01, 0, 0, 0, 0])


def esc_k(page):
    i = page.index(b"\x1biK")
    return page[i + 3]


def test_cut_every_n():
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, cut_every=5)
    assert b"\x1biA\x05" in b
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, auto_cut=False, cut_every=5)
    assert b"\x1biA\x00" in b


def test_cut_every_range():
    for n in (0, 100):
        with pytest.raises(ValueError):
            page_bytes([bytes(16)] * 40, TAPES[12], 2, cut_every=n)


def test_half_cut_and_chain_flags():
    page = lambda **kw: page_bytes([bytes(16)] * 40, TAPES[12], 2, **kw)
    assert esc_k(page()) == 0x08
    assert esc_k(page(half_cut=True)) == 0x0C
    assert esc_k(page(chain=True)) == 0x00
    assert esc_k(page(half_cut=True, chain=True)) == 0x04


def test_half_cut_only_on_models_with_half_cutter():
    b = page_bytes([bytes(16)] * 40, TAPES[12], 2, model=MODELS["PT-E310BT"], half_cut=True)
    assert esc_k(b) == 0x08


def test_chain_ignored_without_cutter():
    m = MODELS["PT-P300BT"]
    b = page_bytes([bytes(16)] * 40, m.tape(12), 0, model=m, chain=True, half_cut=True)
    assert esc_k(b) == 0x08


def test_job_pages_pass_cut_options():
    pages = job_pages([[bytes(16)] * 40] * 2, TAPES[12], cut_every=3, half_cut=True, chain=True)
    assert all(b"\x1biA\x03" in p and esc_k(p) == 0x04 for p in pages)
