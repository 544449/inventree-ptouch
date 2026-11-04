import pytest

from conftest import REAL_STATUS, with_bytes
from inventree_ptouch.protocol import Status
from inventree_ptouch.rules import check_item_fits, check_media, check_template, is_ptouch_template
from inventree_ptouch.tape import TAPES
from inventree_ptouch.transport import PrinterError


def test_template_opt_in_required():
    with pytest.raises(ValueError):
        check_template({})
    with pytest.raises(ValueError):
        check_template({"ptouch_auto_height": "yes"})
    check_template({"ptouch_auto_height": True})


def test_narrow_tape_refuses_large_pk():
    check_item_fits(99999, TAPES[9])
    with pytest.raises(ValueError):
        check_item_fits(100000, TAPES[9])
    check_item_fits(100000, TAPES[12])


def test_check_media_returns_tape():
    assert check_media(Status.parse(REAL_STATUS)) is TAPES[12]


def test_check_media_non_laminated_ok():
    assert check_media(Status.parse(with_bytes(b11=0x03))) is TAPES[12]


def test_check_media_refuses_heat_shrink():
    with pytest.raises(PrinterError, match="(?i)unsupported tape"):
        check_media(Status.parse(with_bytes(b11=0x11)))


def test_check_media_reports_problems():
    with pytest.raises(PrinterError, match="(?i)no media"):
        check_media(Status.parse(with_bytes(b8=0x01)))


def test_check_media_refuses_unknown_width():
    with pytest.raises(PrinterError, match="(?i)width"):
        check_media(Status.parse(with_bytes(b10=36)))


def test_is_ptouch_template():
    assert is_ptouch_template({"ptouch_auto_height": True})
    assert not is_ptouch_template({})
    assert not is_ptouch_template(None)
    assert not is_ptouch_template({"ptouch_auto_height": "true"})


from inventree_ptouch.models import MODELS
from inventree_ptouch.rules import status_text


def test_status_text():
    assert status_text(MODELS["PT-E560BT"], Status.parse(REAL_STATUS)) == "PT-E560BT, 12 mm tape"
    assert status_text(MODELS["PT-E560BT"], Status.parse(with_bytes(b10=4))) == "PT-E560BT, 3.5 mm tape"


from types import SimpleNamespace

from inventree_ptouch.rules import printer_offered


def test_printer_offered_without_template():
    assert printer_offered(None)


def test_printer_offered_only_for_ptouch_templates():
    assert printer_offered(SimpleNamespace(metadata={"ptouch_auto_height": True}))
    assert not printer_offered(SimpleNamespace(metadata=None))
    assert not printer_offered(SimpleNamespace(metadata={}))


def test_check_media_uses_model_tapes():
    p300 = MODELS["PT-P300BT"]
    assert check_media(Status.parse(with_bytes(b4=0x72)), p300) == p300.tape(12)
    with pytest.raises(PrinterError, match="(?i)width"):
        check_media(Status.parse(with_bytes(b4=0x72, b10=18)), p300)


from inventree_ptouch.rules import CUT_SETTINGS, cut_options

MACHINE = {"AUTO_CUT": True, "CUT_EVERY": 3, "HALF_CUT": True, "CHAIN_PRINTING": False}


def test_cut_options_default_to_machine_settings():
    assert cut_options({}, MACHINE.get) == {"auto_cut": True, "cut_every": 3, "half_cut": True, "chain": False}


def test_cut_options_from_print_dialog_win():
    opts = cut_options({"auto_cut": False, "cut_every": 7, "chain": True}, MACHINE.get)
    assert opts == {"auto_cut": False, "cut_every": 7, "half_cut": True, "chain": True}


def test_cut_options_cast_types():
    opts = cut_options({"cut_every": "2"}, {**MACHINE, "HALF_CUT": 0}.get)
    assert opts["cut_every"] == 2 and opts["half_cut"] is False


def test_cut_settings_cover_job_pages_keywords():
    assert set(CUT_SETTINGS) == {"auto_cut", "cut_every", "half_cut", "chain"}
