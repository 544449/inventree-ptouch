import os

from django.db.models.functions import Length

from machine.registry import registry
from machine.models import MachineConfig
from part.models import Part
from report.models import LabelTemplate

from inventree_ptouch.imaging import image_to_lines
from inventree_ptouch.tape import TAPES

OUT = "/tmp/ptouch-check"
os.makedirs(OUT, exist_ok=True)

cfg = MachineConfig.objects.get(name=os.environ.get("PTOUCH_MACHINE_NAME", "P-touch"))
if not registry.ready:
    registry.initialize(main=True)
machine = registry.get_machine(cfg.pk)
print("machine", machine.name, "driver", machine.driver.SLUG, "errors", machine.errors)
driver = machine.driver
tmpl = LabelTemplate.objects.get(name="P-touch Part Label")

by_name = Part.objects.annotate(n=Length("name")).order_by("n")
by_desc = Part.objects.annotate(d=Length("description")).order_by("-d")
parts = [by_name.first(), by_name[by_name.count() // 2], by_desc.first()]
for part in parts:
    for tape in TAPES.values():
        img = driver.render_label(tmpl, part, tape)
        lines = image_to_lines(img, tape)
        path = f"{OUT}/{part.pk}-{tape.width_code}.png"
        img.save(path)
        print(f"part {part.pk:4} {part.name[:20]:20} tape {tape.width_code:2} mm: "
              f"{img.width}x{img.height} px ({img.width * 25.4 / 180:.1f} mm), {len(lines)} lines")

try:
    print("status:", driver.get_status(machine))
except Exception as e:
    print("status: FAILED", type(e).__name__, e)
