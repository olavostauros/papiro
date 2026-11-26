#!/usr/bin/env python3
"""Make reviewed, monochrome working copies; preserve raw SVGs verbatim.

Requires selections.json populated only after visual review. No geometry is
assumed: root child removals and crops must be explicit per selected result.
"""
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from inspect_svg import inspect

ROOT = Path(__file__).resolve().parent
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def normalize(el):
    for key in ("fill", "stroke"):
        value = el.get(key)
        if value is not None and value not in {"none", "transparent"}:
            if "url(" in value.lower():
                raise ValueError("Paint server not supported in monochrome master")
            el.set(key, "currentColor")
    if "style" in el.attrib:
        el.set("style", re.sub(r"(?<![\w-])(fill|stroke)\s*:\s*([^;]+)",
                              lambda m: m.group(0) if m.group(2).strip() in {"none", "transparent"}
                              else f"{m.group(1)}:currentColor", el.get("style")))


def prepare(selection):
    source = ROOT / selection["raw"]
    report = inspect(source)
    if report["errors"]:
        raise ValueError(report["errors"])
    root = ET.fromstring(source.read_text())
    children = list(root)
    for index in sorted(selection.get("remove_root_children", []), reverse=True):
        root.remove(children[index])
    if selection.get("compound_evenodd"):
        paths = list(root)
        if not paths or any(el.tag.split("}")[-1] != "path" for el in paths):
            raise ValueError("Compound conversion requires only direct path children")
        transforms = {el.get("transform", "") for el in paths}
        if len(transforms) != 1:
            raise ValueError("Review distinct transforms before compounding")
        if any(not el.get("d", "").rstrip().lower().endswith("z") for el in paths):
            raise ValueError("Expected closed contours for transparent counterforms")
        # Concatenate exact generated contours: background-coloured overlays
        # become true apertures under the evenodd fill rule. No curve edits.
        combined = ET.Element(f"{{{SVG}}}path", {"d": " ".join(el.get("d") for el in paths),
                              "fill": "currentColor", "fill-rule": "evenodd"})
        transform = next(iter(transforms))
        if transform:
            combined.set("transform", transform)
        for el in paths:
            root.remove(el)
        root.append(combined)
    # Do not turn multi-colour overlays into incorrect filled shapes.
    paints = set()
    for el in root.iter():
        for key in ("fill", "stroke"):
            value = el.get(key)
            if value not in {None, "none", "transparent", "currentColor"}:
                paints.add(value.lower())
        if "style" in el.attrib:
            for m in re.finditer(r"(?:^|;)\s*(fill|stroke)\s*:\s*([^;]+)", el.get("style")):
                if m.group(2).strip() not in {"none", "transparent", "currentColor"}:
                    paints.add(m.group(2).strip().lower())
    if len(paints) > 1:
        raise ValueError(f"Review multiple paints before monochrome conversion: {paints}")
    for el in root.iter():
        normalize(el)
    root.set("fill", "currentColor")
    root.set("color", "#2c471c")
    if "viewBox" in selection:
        root.set("viewBox", " ".join(map(str, selection["viewBox"])))
    root.set("width", "104")
    root.set("height", "104")
    for name in ("aria-labelledby", "role"):
        root.attrib.pop(name, None)
    for el in list(root):
        if el.tag.split("}")[-1] in {"title", "desc"}:
            root.remove(el)
    out = ROOT / "working" / f'{selection["id"]}.svg'
    out.parent.mkdir(exist_ok=True)
    out.write_text(ET.tostring(root, encoding="unicode") + "\n")
    return str(out.relative_to(ROOT))


if __name__ == "__main__":
    config = ROOT / "selections.json"
    if not config.exists():
        raise SystemExit("selections.json is pending visual review; nothing prepared.")
    selections = json.loads(config.read_text())
    for selection in selections:
        print(prepare(selection))
