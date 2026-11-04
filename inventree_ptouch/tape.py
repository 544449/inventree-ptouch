from dataclasses import dataclass

DPI = 180
HEAD_PINS = 128
MAX_LENGTH_12MM = 50.0
BAND_12MM = 70


class UnsupportedTape(ValueError):
    pass


@dataclass(frozen=True)
class Tape:
    width_code: int
    left_pins: int
    band_dots: int

    @property
    def band_mm(self) -> float:
        return self.band_dots * 25.4 / DPI

    @property
    def max_length_mm(self) -> float:
        if self.band_dots <= BAND_12MM:
            return MAX_LENGTH_12MM
        return MAX_LENGTH_12MM * self.band_dots / BAND_12MM


TAPES = {
    4: Tape(4, 52, 24),
    6: Tape(6, 48, 32),
    9: Tape(9, 39, 50),
    12: Tape(12, 29, 70),
    18: Tape(18, 8, 112),
    24: Tape(24, 0, 128),
}


def tape_for_width(width_code: int) -> Tape:
    try:
        return TAPES[width_code]
    except KeyError:
        raise UnsupportedTape(f"unsupported tape width code {width_code} (mm)") from None
