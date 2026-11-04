from .protocol import Status
from .tape import BAND_12MM, Tape, UnsupportedTape, tape_for_width
from .transport import PrinterError

OPT_IN_KEY = "ptouch_auto_height"
MEDIA_OK = {0x01: "laminated", 0x03: "non-laminated"}
NARROW_MAX_PK = 99999
CUT_SETTINGS = {"auto_cut": "AUTO_CUT", "cut_every": "CUT_EVERY", "half_cut": "HALF_CUT", "chain": "CHAIN_PRINTING"}


def is_ptouch_template(metadata: dict | None) -> bool:
    return bool(metadata) and metadata.get(OPT_IN_KEY) is True


def printer_offered(label) -> bool:
    return label is None or is_ptouch_template(label.metadata)


def check_template(metadata: dict) -> None:
    if not is_ptouch_template(metadata):
        raise ValueError(
            f"label template is not a P-touch auto-height template "
            f"(metadata '{OPT_IN_KEY}' must be true)")


def check_item_fits(pk: int, tape: Tape) -> None:
    if tape.band_dots < BAND_12MM and pk > NARROW_MAX_PK:
        raise ValueError(
            f"part {pk}: id too large for the Data Matrix on {tape.width_code} mm tape, "
            f"use 12 mm or wider tape")


def status_text(model, status: Status) -> str:
    width = "3.5" if status.media_width == 4 else str(status.media_width)
    return f"{model.name}, {width} mm tape"


def check_media(status: Status, model=None) -> Tape:
    problems = status.problems()
    if problems:
        raise PrinterError("printer reports: " + ", ".join(problems))
    if status.media_type not in MEDIA_OK:
        raise PrinterError(f"unsupported tape type 0x{status.media_type:02x}, use TZe laminated tape")
    try:
        return model.tape(status.media_width) if model else tape_for_width(status.media_width)
    except UnsupportedTape as e:
        raise PrinterError(f"unsupported tape width {status.media_width} mm") from e


def cut_options(options: dict, setting) -> dict:
    out = {key: options.get(key, setting(name)) for key, name in CUT_SETTINGS.items()}
    out["cut_every"] = int(out["cut_every"])
    for key in ("auto_cut", "half_cut", "chain"):
        out[key] = bool(out[key])
    return out
