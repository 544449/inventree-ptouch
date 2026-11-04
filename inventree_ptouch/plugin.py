import copy

from django.db import models
from django.utils.translation import gettext_lazy as _

from plugin import InvenTreePlugin
from plugin.machine.machine_types import LabelPrinterBaseDriver, LabelPrinterMachine
from plugin.mixins import MachineDriverMixin
from report.models import LabelTemplate
from rest_framework import serializers

from . import VERSION
from .imaging import fit_band, image_to_lines, trim_right
from .models import AUTO, MODELS, Model, resolve_model
from .protocol import MAX_CUT_EVERY, Status, job_pages
from .rules import (CUT_SETTINGS, check_item_fits, check_media, check_template, cut_options, printer_offered,
                    status_text)
from .tape import DPI, Tape, UnsupportedTape
from .transport import PrinterError, PrinterUnreachable, RfcommLink, print_pages, query_status

STATUS = LabelPrinterMachine.MACHINE_STATUS
IDLE_TEXT = "status is read when printing or on Restart"


class PtouchPlugin(MachineDriverMixin, InvenTreePlugin):
    NAME = "BrotherPtouch"
    SLUG = "ptouch"
    TITLE = "Brother P-touch (Bluetooth)"
    DESCRIPTION = "Bluetooth label printing on Brother P-touch printers"
    VERSION = VERSION
    AUTHOR = "inventree-ptouch contributors"
    MIN_VERSION = "1.0.0"

    def get_machine_drivers(self) -> list:
        return [PtouchBtDriver]


def model_choices(**kwargs):
    out = [(AUTO, _("Auto-detect"))]
    for m in MODELS.values():
        out.append((m.name, m.name if m.verified else f"{m.name} (untested)"))
    return out


class PtouchBtDriver(LabelPrinterBaseDriver):
    SLUG = "ptouch-bt"
    NAME = "Brother P-touch (Bluetooth)"
    DESCRIPTION = "Brother P-touch over Bluetooth RFCOMM, tape width auto-detected"

    MACHINE_SETTINGS = {
        "BT_ADDRESS": {
            "name": _("Bluetooth address"),
            "description": _("MAC address of the paired printer, e.g. 00:11:22:33:44:55"),
            "required": True,
        },
        "MODEL": {
            "name": _("Printer model"),
            "description": _("Auto-detect works for PT-E560BT, PT-E310BT and PT-P300BT; select other models"),
            "choices": model_choices,
            "default": AUTO,
        },
        "RFCOMM_CHANNEL": {
            "name": _("RFCOMM channel"),
            "description": _("Serial port channel of the printer (2 on the PT-E560BT)"),
            "validator": int,
            "default": 2,
        },
        "CONNECT_TIMEOUT": {
            "name": _("Connect timeout"),
            "description": _("Seconds to wait for the printer to answer"),
            "validator": int,
            "default": 10,
        },
        "AUTO_CUT": {
            "name": _("Auto cut"),
            "description": _("Cut after each label"),
            "validator": bool,
            "default": True,
        },
        "CUT_EVERY": {
            "name": _("Cut every"),
            "description": _("Cut after every n labels (1-99), needs auto cut"),
            "validator": int,
            "default": 1,
        },
        "HALF_CUT": {
            "name": _("Half cut"),
            "description": _("Half-cut between labels (PT-E560BT)"),
            "validator": bool,
            "default": False,
        },
        "CHAIN_PRINTING": {
            "name": _("Chain printing"),
            "description": _("No feed and cut after the last label; saves tape, the last label comes out with the next job"),
            "validator": bool,
            "default": False,
        },
    }

    class PrintingOptionsSerializer(LabelPrinterBaseDriver.PrintingOptionsSerializer):
        auto_cut = serializers.BooleanField(default=True, label=_("Auto cut"))
        cut_every = serializers.IntegerField(default=1, min_value=1, max_value=MAX_CUT_EVERY, label=_("Cut every"))
        half_cut = serializers.BooleanField(default=False, label=_("Half cut"))
        chain = serializers.BooleanField(default=False, label=_("Chain printing"))

        def __init__(self, machine=None, *args, **kwargs):
            super().__init__(machine, *args, **kwargs)
            if machine:
                for key, name in CUT_SETTINGS.items():
                    self.fields[key].default = machine.get_setting(name, "D")

    def init_machine(self, machine: LabelPrinterMachine):
        machine.set_status(STATUS.UNKNOWN)
        machine.set_status_text(IDLE_TEXT)

    def restart_machine(self, machine: LabelPrinterMachine):
        try:
            with self._link(machine) as link:
                status = query_status(link)
            model = self._model(machine, status)
            check_media(status, model)
        except PrinterUnreachable as e:
            self._fail(machine, STATUS.DISCONNECTED, e)
            return
        except (PrinterError, UnsupportedTape, ValueError) as e:
            self._fail(machine, STATUS.ERROR, e)
            return
        machine.reset_errors()
        machine.set_status(STATUS.CONNECTED)
        machine.set_status_text(status_text(model, status))

    def _link(self, machine: LabelPrinterMachine) -> RfcommLink:
        return RfcommLink(
            machine.get_setting("BT_ADDRESS", "D"),
            channel=int(machine.get_setting("RFCOMM_CHANNEL", "D")),
            timeout=float(machine.get_setting("CONNECT_TIMEOUT", "D")),
        )

    def _model(self, machine: LabelPrinterMachine, status: Status) -> Model:
        return resolve_model(machine.get_setting("MODEL", "D") or AUTO, status.model)

    def get_printers(self, label: LabelTemplate, items, **kwargs):
        if not printer_offered(label):
            return []
        return super().get_printers(label, items, **kwargs)

    def get_status(self, machine: LabelPrinterMachine) -> Status:
        with self._link(machine) as link:
            return query_status(link)

    def render_label(self, label: LabelTemplate, item: models.Model, tape: Tape):
        sized = copy.copy(label)
        sized.height = tape.band_mm
        sized.width = tape.max_length_mm
        img = self.render_to_png(sized, item, dpi=DPI)
        if img is None:
            raise ValueError(f"rendering label '{label.name}' failed")
        return trim_right(fit_band(img, tape))

    def print_label(self, machine, label, item, **kwargs):
        self.print_labels(machine, label, [item], **kwargs)

    def print_labels(self, machine: LabelPrinterMachine, label: LabelTemplate, items, **kwargs):
        options = kwargs.get("printing_options", {}) or {}
        copies = max(1, int(options.get("copies", 1)))
        cuts = cut_options(options, lambda name: machine.get_setting(name, "D"))
        try:
            check_template(label.metadata or {})
            with self._link(machine) as link:
                status = query_status(link)
                model = self._model(machine, status)
                tape = check_media(status, model)
                pages = []
                for item in items:
                    check_item_fits(item.pk, tape)
                    lines = image_to_lines(self.render_label(label, item, tape), tape)
                    pages += [lines] * copies
                machine.set_status(STATUS.PRINTING)
                print_pages(link, job_pages(pages, tape, model=model, media_type=status.media_type, **cuts))
        except PrinterUnreachable as e:
            self._fail(machine, STATUS.DISCONNECTED, e)
            raise
        except (PrinterError, UnsupportedTape, ValueError) as e:
            self._fail(machine, STATUS.ERROR, e)
            raise
        machine.reset_errors()
        machine.set_status(STATUS.CONNECTED)
        machine.set_status_text(status_text(model, status))

    def _fail(self, machine: LabelPrinterMachine, status, error: Exception):
        machine.handle_error(str(error))
        machine.set_status(status)
        machine.set_status_text(str(error))
