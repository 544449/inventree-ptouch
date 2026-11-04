import pytest
from PIL import Image

from inventree_ptouch.imaging import fit_band, image_to_lines, trim_right
from inventree_ptouch.tape import TAPES


def test_image_to_lines_top_left_pixel():
    img = Image.new("L", (40, 70), 255)
    img.putpixel((0, 0), 0)
    lines = image_to_lines(img, TAPES[12])
    assert len(lines) == 40 and lines[0][3] == 0x04 and lines[1] == bytes(16)


def test_image_to_lines_threshold_and_rgb():
    img = Image.new("RGB", (34, 70), (255, 255, 255))
    img.putpixel((0, 0), (100, 100, 100))
    img.putpixel((1, 0), (200, 200, 200))
    lines = image_to_lines(img, TAPES[12])
    assert lines[0][3] == 0x04 and lines[1] == bytes(16)


def test_image_to_lines_rejects_wrong_height():
    with pytest.raises(ValueError):
        image_to_lines(Image.new("L", (40, 60), 255), TAPES[12])


def test_fit_band_pads_and_crops():
    assert fit_band(Image.new("L", (50, 71), 255), TAPES[12]).height == 70
    assert fit_band(Image.new("L", (50, 69), 255), TAPES[12]).height == 70
    with pytest.raises(ValueError):
        fit_band(Image.new("L", (50, 100), 255), TAPES[12])


def test_fit_band_padding_is_white():
    out = fit_band(Image.new("L", (50, 68), 0), TAPES[12])
    assert out.getpixel((0, 69)) == 255 and out.getpixel((0, 0)) == 0


def test_trim_right_keeps_content_plus_margin():
    img = Image.new("L", (354, 70), 255)
    img.putpixel((100, 10), 0)
    assert trim_right(img).width == 108


def test_trim_right_min_length():
    img = Image.new("L", (354, 70), 255)
    img.putpixel((3, 10), 0)
    assert trim_right(img).width == 34


def test_trim_never_exceeds_input():
    img = Image.new("L", (354, 70), 0)
    assert trim_right(img).width == 354


def test_light_grey_antialias_counts_as_black():
    img = Image.new("L", (34, 70), 255)
    img.putpixel((0, 0), 150)
    img.putpixel((1, 0), 175)
    lines = image_to_lines(img, TAPES[12])
    assert lines[0][3] == 0x04 and lines[1] == bytes(16)
