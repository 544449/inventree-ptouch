# Read-only preview of the part label template on the server, as InvenTree renders it.
# Copy the template to /tmp/ptouch_part_label.html, then: deploy/run_django.sh deploy/preview_template.py
import os

import pdf2image
from django.db.models.functions import Length
from django.template import engines
from weasyprint import HTML

from part.models import Part
from report.fetcher import InvenTreeURLFetcher
from report.models import LabelTemplate

SRC = os.environ.get("PTOUCH_TEMPLATE", "/tmp/ptouch_part_label.html")
OUT = "/tmp/ptouch-preview"
DPI = 180
TAPES = {4: 24, 6: 32, 9: 50, 12: 70, 18: 112, 24: 128}

os.makedirs(OUT, exist_ok=True)
with open(SRC, encoding="utf-8") as f:
    template = engines["django"].from_string(f.read())

by_name = Part.objects.annotate(n=Length("name")).filter(n__gt=0).order_by("n", "pk")
by_desc = Part.objects.annotate(d=Length("description")).order_by("-d", "pk")
parts = [by_name.first(), by_name[by_name.count() // 2], by_desc.first()]
if os.environ.get("PTOUCH_PARTS"):
    parts = [Part.objects.get(pk=int(pk)) for pk in os.environ["PTOUCH_PARTS"].split(",")]

for part in parts:
    print(f"part {part.pk}: name {len(part.name)} chars {part.name!r}, "
          f"description {len(part.description)} chars")
    for tape, dots in TAPES.items():
        height = dots * 25.4 / DPI
        width = 50.0 if dots <= 70 else 50.0 * dots / 70
        label = LabelTemplate(name="ptouch preview", width=width, height=height,
                              model_type="part")
        html = template.render(label.get_context(part))
        pdf = HTML(string=html, url_fetcher=InvenTreeURLFetcher()).write_pdf(pdf_forms=True)
        img = pdf2image.convert_from_bytes(pdf, dpi=DPI, use_pdftocairo=True)[0]
        path = f"{OUT}/{part.pk}-{tape}.png"
        img.save(path)
        print(f"  {tape:2} mm: {img.width} x {img.height} px "
              f"(band {dots}, max {round(width * DPI / 25.4)}) -> {path}")
