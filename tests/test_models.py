import pytest

from inventree_ptouch.models import AUTO, MODELS, resolve_model
from inventree_ptouch.transport import PrinterError


def test_model_table():
    assert set(MODELS) == {"PT-E560BT", "PT-E310BT", "PT-P710BT", "PT-D460BT", "PT-D610BT", "PT-E720BT", "PT-P300BT"}
    assert MODELS["PT-E560BT"].codes == (0x7F,) and MODELS["PT-E560BT"].verified
    assert MODELS["PT-E310BT"].codes == (0x7D,)
    assert [m.name for m in MODELS.values() if m.verified] == ["PT-E560BT"]


def test_auto_detects_known_codes():
    assert resolve_model(AUTO, 0x7F) is MODELS["PT-E560BT"]
    assert resolve_model(AUTO, 0x7D) is MODELS["PT-E310BT"]


def test_auto_unknown_code_asks_for_model():
    with pytest.raises(PrinterError, match="(?i)0x76.*select"):
        resolve_model(AUTO, 0x76)


def test_explicit_model_for_unknown_code():
    assert resolve_model("PT-P710BT", 0x76) is MODELS["PT-P710BT"]


def test_explicit_model_contradicting_known_code():
    with pytest.raises(PrinterError, match="PT-E560BT"):
        resolve_model("PT-E310BT", 0x7F)


def test_explicit_unknown_name():
    with pytest.raises(ValueError):
        resolve_model("PT-9999", 0x7F)


from inventree_ptouch.tape import Tape, UnsupportedTape


def test_p300bt_auto_detected():
    assert resolve_model(AUTO, 0x72) is MODELS["PT-P300BT"]


def test_p300bt_tape_table_middle_64_dots():
    m = MODELS["PT-P300BT"]
    assert m.tape(12) == Tape(12, 32, 64)
    with pytest.raises(UnsupportedTape):
        m.tape(18)


def test_other_models_use_standard_tapes():
    assert MODELS["PT-E560BT"].tape(24) == Tape(24, 0, 128)


def test_half_cutter_only_on_e560bt():
    assert [m.name for m in MODELS.values() if m.half_cut] == ["PT-E560BT"]
