from dataclasses import dataclass
from typing import Sequence

from .models import MODELS, Model
from .tape import HEAD_PINS, Tape

INVALIDATE = b"\x00" * 200
INIT = b"\x1b@"
STATUS_REQUEST = b"\x1biS"

STATUS_HEADER = b"\x80\x20\x42\x30"
STATUS_SIZE = 32

ERR1 = {0x01: "no media", 0x04: "cutter jam", 0x10: "printer in use"}
ERR2 = {
    0x01: "replace media",
    0x04: "communication error",
    0x08: "communication buffer full",
    0x10: "cover open",
    0x20: "overheating",
    0x80: "system error",
}
MEDIA_NONE = 0x00
MEDIA_INCOMPATIBLE = 0xFF
EXT_INCOMPATIBLE = 0x21


@dataclass
class Status:
    model: int
    ext_error: int
    err1: int
    err2: int
    media_width: int
    media_type: int
    status_type: int
    phase_type: int

    @classmethod
    def parse(cls, data: bytes) -> "Status":
        if len(data) != STATUS_SIZE or not data.startswith(STATUS_HEADER):
            raise ValueError(f"not a printer status packet: {data[:8].hex(' ')}")
        return cls(
            model=data[4],
            ext_error=data[7],
            err1=data[8],
            err2=data[9],
            media_width=data[10],
            media_type=data[11],
            status_type=data[18],
            phase_type=data[19],
        )

    def problems(self) -> list[str]:
        out = [msg for bit, msg in ERR1.items() if self.err1 & bit]
        out += [msg for bit, msg in ERR2.items() if self.err2 & bit]
        if self.ext_error == EXT_INCOMPATIBLE or self.media_type == MEDIA_INCOMPATIBLE:
            out.append("incompatible tape")
        if (self.media_type == MEDIA_NONE or self.media_width == 0) and "no media" not in out:
            out.append("no media")
        return out


def raster_line(column: Sequence[int], tape: Tape) -> bytes:
    if len(column) != tape.band_dots:
        raise ValueError(f"column has {len(column)} dots, tape band is {tape.band_dots}")
    line = bytearray(HEAD_PINS // 8)
    for r, black in enumerate(column):
        if black:
            pin = tape.left_pins + r
            line[pin // 8] |= 0x80 >> (pin % 8)
    return bytes(line)


MIN_LINES = 34
MAX_LINES = 7087
MAX_CUT_EVERY = 99
HALF_CUT = 0x04
NO_CHAIN = 0x08
FIRST_PAGE, MIDDLE_PAGE, LAST_PAGE = 0, 1, 2
DEFAULT_MODEL = MODELS["PT-E560BT"]


def advanced_mode(model: Model, half_cut: bool, chain: bool) -> int:
    flags = 0 if chain and model.has_cutter else NO_CHAIN
    if half_cut and model.half_cut:
        flags |= HALF_CUT
    return flags


def page_bytes(lines: list[bytes], tape: Tape, position: int, auto_cut: bool = True,
               model: Model = DEFAULT_MODEL, last: bool | None = None, media_type: int = 0,
               cut_every: int = 1, half_cut: bool = False, chain: bool = False) -> bytes:
    n = len(lines)
    if not MIN_LINES <= n <= MAX_LINES:
        raise ValueError(f"label is {n} dots long, must be {MIN_LINES}..{MAX_LINES}")
    if not 1 <= cut_every <= MAX_CUT_EVERY:
        raise ValueError(f"cut every {cut_every} labels, must be 1..{MAX_CUT_EVERY}")
    if last is None:
        last = position == LAST_PAGE
    out = bytearray()
    out += b"\x1bia\x01"
    if model.status_notify:
        out += b"\x1bi!\x00"
    if model.info_cmd:
        kind = media_type if model.info_media_type else 0x00
        out += b"\x1biz" + bytes([model.info_valid, kind, tape.width_code, 0x00]) + n.to_bytes(4, "little")
        out += bytes([position, 0x00])
    out += b"\x1biM" + (b"\x40" if auto_cut and model.has_cutter else b"\x00")
    if model.cut_each:
        out += b"\x1biA" + bytes([cut_every if auto_cut else 0])
    if model.advanced:
        out += b"\x1biK" + bytes([advanced_mode(model, half_cut, chain)])
    if model.margin_dots is not None:
        out += b"\x1bid" + model.margin_dots.to_bytes(2, "little")
    out += b"M\x02" if model.packbits else b"M\x00"
    for line in lines:
        if len(line) != HEAD_PINS // 8:
            raise ValueError("raster line must be 16 bytes")
        if not any(line) and (model.packbits or model.zero_lines):
            out += b"Z"
        elif model.packbits:
            out += b"G\x11\x00" + bytes([len(line) - 1]) + line
        else:
            out += b"G\x10\x00" + line
    out += b"\x1a" if last else b"\x0c"
    return bytes(out)


def page_position(i: int, count: int, model: Model) -> int:
    if model.last_page_code == LAST_PAGE and i == count - 1:
        return LAST_PAGE
    return FIRST_PAGE if i == 0 else MIDDLE_PAGE


def job_pages(pages: list[list[bytes]], tape: Tape, auto_cut: bool = True,
              model: Model = DEFAULT_MODEL, media_type: int = 0, cut_every: int = 1,
              half_cut: bool = False, chain: bool = False) -> list[bytes]:
    count = len(pages)
    return [
        page_bytes(lines, tape, page_position(i, count, model), auto_cut, model,
                   last=i == count - 1, media_type=media_type, cut_every=cut_every,
                   half_cut=half_cut, chain=chain)
        for i, lines in enumerate(pages)
    ]
