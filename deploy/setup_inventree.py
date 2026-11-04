import os
from importlib import resources

from django.core.files.base import ContentFile

from machine.models import MachineConfig, MachineSetting
from plugin.models import PluginConfig
from report.models import LabelTemplate

TEMPLATES = [
    ("P-touch Part Label", "part", "ptouch_part_label.html",
     "Brother PT-E560BT part label, height follows the loaded tape"),
    ("P-touch Location Label", "stocklocation", "ptouch_location_label.html",
     "Brother P-touch stock location label, height follows the loaded tape"),
]
MACHINE_NAME = os.environ.get("PTOUCH_MACHINE_NAME", "P-touch")
BT_ADDRESS = os.environ["PTOUCH_BT_ADDRESS"]
DRIVER = "ptouch-bt"

cfg = PluginConfig.objects.filter(key="ptouch").first()
if cfg is None:
    raise SystemExit("plugin 'ptouch' not registered - did deploy.sh run and the server restart?")
if not cfg.active:
    cfg.active = True
    cfg.save()
print("plugin ptouch active:", cfg.active)

for name, model_type, filename, description in TEMPLATES:
    html = resources.files("inventree_ptouch").joinpath(f"templates/{filename}").read_bytes()
    tmpl = LabelTemplate.objects.filter(name=name).first()
    created = tmpl is None
    if created:
        tmpl = LabelTemplate(name=name, model_type=model_type)
    tmpl.description = description
    tmpl.width = 50
    tmpl.height = round(70 * 25.4 / 180, 4)
    tmpl.enabled = True
    tmpl.template.save(filename, ContentFile(html), save=False)
    tmpl.save()
    tmpl.set_metadata("ptouch_auto_height", True)
    print("template", "created" if created else "updated", tmpl.pk, tmpl.template.name,
          f"{tmpl.width}x{tmpl.height} mm", tmpl.metadata)

machine, created = MachineConfig.objects.get_or_create(
    name=MACHINE_NAME,
    defaults={"machine_type": "label-printer", "driver": DRIVER, "active": True},
)
if machine.driver != DRIVER:
    print("machine driver", machine.driver, "->", DRIVER)
    machine.driver = DRIVER
    machine.save()
MachineSetting.objects.update_or_create(
    machine_config=machine, config_type="D", key="BT_ADDRESS", defaults={"value": BT_ADDRESS})
print("machine", "created" if created else "exists", machine.pk, machine.driver,
      [(s.config_type, s.key, s.value) for s in MachineSetting.objects.filter(machine_config=machine)])
