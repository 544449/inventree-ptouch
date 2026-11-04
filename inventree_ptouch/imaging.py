from PIL import Image

from .protocol import raster_line
from .tape import Tape

BLACK_BELOW = 170
MAX_HEIGHT_SLACK = 2


def fit_band(img: Image.Image, tape: Tape) -> Image.Image:
    img = img.convert("L")
    diff = img.height - tape.band_dots
    if abs(diff) > MAX_HEIGHT_SLACK:
        raise ValueError(f"rendered label is {img.height} dots high, tape band is {tape.band_dots}")
    if diff == 0:
        return img
    out = Image.new("L", (img.width, tape.band_dots), 255)
    out.paste(img.crop((0, 0, img.width, min(img.height, tape.band_dots))), (0, 0))
    return out


def trim_right(img: Image.Image, margin_dots: int = 7, min_dots: int = 34) -> Image.Image:
    img = img.convert("L")
    ink = img.point(lambda v: 255 if v < BLACK_BELOW else 0).getbbox()
    last = ink[2] if ink else 0
    width = min(img.width, max(min_dots, last + margin_dots))
    return img.crop((0, 0, width, img.height))


def image_to_lines(img: Image.Image, tape: Tape) -> list[bytes]:
    img = img.convert("L")
    if img.height != tape.band_dots:
        raise ValueError(f"image is {img.height} dots high, tape band is {tape.band_dots}")
    px = img.load()
    return [
        raster_line([px[x, y] < BLACK_BELOW for y in range(img.height)], tape)
        for x in range(img.width)
    ]
