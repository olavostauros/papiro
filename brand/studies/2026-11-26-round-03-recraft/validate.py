#!/usr/bin/env python3
"""Validate delivered vector assets and exact preservation of the wordmark."""
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from inspect_svg import inspect

ROOT = Path(__file__).resolve().parent
source = (ROOT / "../2026-11-26/01-nome/papiro.svg").read_text()
word = source[source.index("<g "):source.rindex("</g>") + 4]
config = ROOT / "selections.json"
if not config.exists():
    raise SystemExit("No reviewed selections yet; validation pending.")
selected = json.loads(config.read_text())
paths = [p for s in selected for p in sorted((ROOT / s["id"]).glob("*.svg"))]
paths += [ROOT / "comparison.svg", ROOT / "reductions.svg"]
assert len(paths) == 14, f"Expected 14 SVGs, found {len(paths)}"
letters = 0
for path in paths:
    report = inspect(path)
    assert not report["errors"], (path, report["errors"])
    box = [float(x) for x in report["viewBox"].replace(",", " ").split()]
    assert len(box) == 4 and all(math.isfinite(x) for x in box) and box[2] > 0 and box[3] > 0, path
    text = path.read_text()
    if path.parent.name in {s["id"] for s in selected}:
        parsed = ET.fromstring(text)
        assert not any("color" in el.attrib for el in list(parsed.iter())[1:]), f"Nested colour override: {path}"
    if path.name.startswith("papiro"):
        assert word in text, f"Wordmark changed: {path}"
        letters += 1
assert letters == 6
for selection in selected:
    original_root = ET.fromstring((ROOT / selection["raw"]).read_text())
    expected = " ".join(el.get("d") for i, el in enumerate(original_root)
                        if i not in selection["remove_root_children"])
    working = ET.fromstring((ROOT / "working" / f'{selection["id"]}.svg').read_text())
    assert len(working) == 1 and working[0].get("d") == expected, "Generated contours changed"
    assert working[0].get("fill-rule") == "evenodd"
pngs = [ROOT / s["id"] / name for s in selected for name in ("papiro.png", "mark.png")]
for path in pngs:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    width, height, depth, color = struct.unpack(">IIBB", data[16:26])
    assert color == 6, f"Expected RGBA PNG, got color type {color}: {path}"
    assert width == (1200 if path.name == "papiro.png" else 416), path
    assert height > 0 and depth == 8, path
print("Validated 14 SVGs, six exact wordmark groups and four RGBA PNGs.")
