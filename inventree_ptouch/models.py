from dataclasses import dataclass, field

from .errors import PrinterError
from .tape import TAPES, Tape, UnsupportedTape

AUTO = "auto"
REF_E3E5 = "Brother Raster Command Reference PT-E310BT/E510/E560BT 1.00"
REF_P710 = "Brother Raster Command Reference PT-E550W/P750W/P710BT 1.02"
REF_PTOUCH_RS = "ptouch-rs device table (no Brother reference published)"
REF_P300 = "ptouch-rs p300bt.rs (hardware-verified) and stecman's PT-P300BT gist"


@dataclass(frozen=True)
class Model:
    name: str
    codes: tuple
    max_tape_mm: int
    source: str
    verified: bool = False
    status_notify: bool = True
    info_cmd: bool = True
    info_valid: int = 0x84
    info_media_type: bool = False
    cut_each: bool = True
    advanced: bool = True
    margin_dots: int | None = 14
    packbits: bool = False
    zero_lines: bool = False
    has_cutter: bool = True
    half_cut: bool = False
    last_page_code: int = 2
    tapes: dict = field(default=None, compare=False, hash=False)

    def tape(self, width_code: int) -> Tape:
        table = self.tapes or TAPES
        if width_code not in table:
            raise UnsupportedTape(f"{self.name}: unsupported tape width code {width_code} (mm)")
        return table[width_code]


MODELS = {m.name: m for m in (
    Model("PT-E560BT", (0x7F,), 24, REF_E3E5, verified=True, half_cut=True),
    Model("PT-E310BT", (0x7D,), 18, REF_E3E5),
    Model("PT-P710BT", (), 24, REF_P710, cut_each=False, last_page_code=1),
    Model("PT-D460BT", (), 18, REF_PTOUCH_RS, status_notify=False, cut_each=False, advanced=False, margin_dots=1),
    Model("PT-D610BT", (), 24, REF_PTOUCH_RS, status_notify=False, cut_each=False, advanced=False, margin_dots=1),
    Model("PT-E720BT", (), 24, REF_PTOUCH_RS, status_notify=False, info_cmd=False, cut_each=False,
          advanced=False, margin_dots=None, packbits=True),
    Model("PT-P300BT", (0x72,), 12, REF_P300, status_notify=False, info_valid=0xC4, info_media_type=True,
          cut_each=False, margin_dots=0, zero_lines=True, has_cutter=False, last_page_code=1,
          tapes={12: Tape(12, 32, 64)}),
)}
BY_CODE = {code: m for m in MODELS.values() for code in m.codes}


def resolve_model(setting: str, model_code: int) -> Model:
    detected = BY_CODE.get(model_code)
    if setting in (None, "", AUTO):
        if detected is None:
            raise PrinterError(
                f"unknown P-touch model code 0x{model_code:02x}: select the printer model "
                f"in the machine settings")
        return detected
    if setting not in MODELS:
        raise ValueError(f"unknown printer model '{setting}'")
    if detected is not None and detected.name != setting:
        raise PrinterError(
            f"printer reports itself as {detected.name}, but the machine is set to {setting}")
    return MODELS[setting]
