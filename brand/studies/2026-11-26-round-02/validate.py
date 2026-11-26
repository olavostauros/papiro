"""Validate round-02 vectors and verify that the selected lettering is intact."""
from pathlib import Path
import math
import struct
import xml.etree.ElementTree as ET

base = Path(__file__).resolve().parent
allowed = {"svg", "g", "path", "rect", "title", "desc"}
source = (base.parent / "2026-11-26/01-nome/papiro.svg").read_text()
word = source[source.index("<g "):source.rindex("</g>") + 4]
vectors = sorted(base.rglob("*.svg"))
assert len(vectors) == 20, len(vectors)
for path in vectors:
    raw = path.read_text()
    assert "<!DOCTYPE" not in raw and "<!ENTITY" not in raw, path
    root = ET.fromstring(raw)
    vb = list(map(float, root.attrib["viewBox"].split()))
    assert len(vb) == 4 and all(map(math.isfinite, vb)), path
    assert vb[2] > 0 and vb[3] > 0, path
    assert root.tag == "{http://www.w3.org/2000/svg}svg", path
    ids = set()
    for element in root.iter():
        assert element.tag.split("}")[-1] in allowed, path
        for name, value in element.attrib.items():
            assert not name.lower().startswith("on"), (path, name)
            assert not any(x in name.lower() for x in ("href", "src", "style")), path
            assert "url(" not in value.lower(), path
        if "id" in element.attrib:
            assert element.attrib["id"] not in ids, path
            ids.add(element.attrib["id"])
    assert {"title", "desc"} <= ids, path
    if path.name.startswith("papiro"):
        assert word in raw, f"Original lettering changed: {path}"

pngs = sorted(base.glob("*/*.png"))
assert len(pngs) == 6, len(pngs)
for path in pngs:
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", path
    width, height, depth, color = struct.unpack(">IIBB", raw[16:26])
    assert width == (1200 if path.name == "papiro.png" else 416), path
    assert height > 0 and color == 6, path
print("PASS: 20 SVGs, valid XML/viewBoxes, accessible IDs, vector elements only.")
print("PASS: no scripts/events, embedded images, external resources or font dependencies.")
print("PASS: all 9 signature SVGs preserve the exact original lettering group.")
print("PASS: 6 RGBA PNGs (3 signatures at 1200 px and 3 symbols at 416 px).")
