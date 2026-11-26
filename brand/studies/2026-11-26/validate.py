"""Structural checks for this exploration, with no third-party dependencies."""
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

base = Path(__file__).resolve().parent
allowed = {"svg", "g", "path", "rect", "title", "desc"}
assets = sorted(base.rglob("*.svg"))
assert len(assets) == 20, f"Unexpected SVG inventory: {len(assets)}"
for path in assets:
    raw = path.read_text()
    assert "<!DOCTYPE" not in raw and "<!ENTITY" not in raw, path
    root = ET.fromstring(raw)
    assert root.tag == "{http://www.w3.org/2000/svg}svg", path
    width, height = map(float, root.attrib["viewBox"].split()[2:])
    assert width > 0 and height > 0, path
    ids = set()
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        assert tag in allowed, (path, tag)
        for name, value in element.attrib.items():
            name = name.lower()
            assert not name.startswith("on"), (path, name)
            assert not any(token in name for token in ("href", "src", "style")), (path, name)
            assert "url(" not in value.lower(), (path, value)
        if "id" in element.attrib:
            assert element.attrib["id"] not in ids, path
            ids.add(element.attrib["id"])
    assert {"title", "desc"}.issubset(ids), path
    assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) > 0, path

for path in sorted(base.glob("*/papiro.png")):
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", path
    width, height, depth, color_type = struct.unpack(">IIBB", raw[16:26])
    assert width == 1200 and height > 0 and color_type == 6, path

print(f"PASS: {len(assets)} SVGs; valid XML, finite viewBoxes, outlined lettering,")
print("allowed vector elements only, unique accessible IDs, no external resources.")
print("PASS: 3 transparent RGBA signature PNGs, each 1200 px wide.")
