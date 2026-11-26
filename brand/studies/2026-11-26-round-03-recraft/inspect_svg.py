#!/usr/bin/env python3
"""Inspect generated SVGs without rendering or changing the originals."""
from collections import Counter
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ALLOWED = {"svg", "g", "path", "rect", "circle", "ellipse", "polygon", "polyline", "line", "title", "desc", "defs", "clipPath", "metadata", "manifest"}


def inspect(path):
    path = path.resolve()
    source = path.read_text()
    errors = []
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", source, re.I):
        errors.append("Forbidden XML declaration/entity/stylesheet")
    root = ET.fromstring(source)
    if root.tag.split("}")[-1] != "svg":
        errors.append("Root is not SVG")
    tags, paints, styles, ids = Counter(), Counter(), [], []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        tags[tag] += 1
        if tag not in ALLOWED:
            errors.append(f"Unsupported element: {tag}")
        if tag == "manifest" and el.tag != "{http://c2pa.org/manifest}manifest":
            errors.append("Unrecognised manifest namespace")
        for key, value in el.attrib.items():
            local = key.split("}")[-1]
            if local.lower().startswith("on") or local in {"href", "src", "filter", "mask"}:
                errors.append(f"Forbidden attribute: {local}")
            if re.search(r"(?:https?:|data:|javascript:|@import|@font-face)", value, re.I):
                errors.append(f"External or active value in {local}")
            if "url(" in value.lower() and not re.fullmatch(r"url\(#[A-Za-z_][\w.-]*\)", value):
                errors.append(f"External/complex URL in {local}")
            if local == "id":
                ids.append(value)
            if local in {"fill", "stroke"}:
                paints[value] += 1
            if local == "style":
                styles.append(value)
                for match in re.finditer(r"(?:^|;)\s*(fill|stroke)\s*:\s*([^;]+)", value):
                    paints[match.group(2).strip()] += 1
    duplicates = [key for key, n in Counter(ids).items() if n > 1]
    if duplicates:
        errors.append(f"Duplicate IDs: {duplicates}")
    report = {"file": str(path.relative_to(ROOT)), "viewBox": root.get("viewBox"),
              "width": root.get("width"), "height": root.get("height"),
              "elements": dict(tags), "paints": dict(paints), "styles": styles,
              "root_children": [{"index": i, "tag": el.tag.split("}")[-1],
                                 "attributes": {k: (v[:160] + "…" if len(v) > 160 else v) for k, v in el.attrib.items()}}
                                for i, el in enumerate(root)], "errors": sorted(set(errors))}
    return report


if __name__ == "__main__":
    paths = [Path(arg).resolve() for arg in sys.argv[1:]] or sorted((ROOT / "raw").glob("*.svg"))
    if not paths:
        raise SystemExit("No raw SVGs available; no output produced.")
    reports = [inspect(path) for path in paths]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    raise SystemExit(any(report["errors"] for report in reports))
