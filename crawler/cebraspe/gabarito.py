"""Parse Cebraspe gabarito PDFs with pdftotext -layout (free, exact).

Two formats seen in the wild:
- certo/errado: `Item   1 2 3...` line followed by `Gabarito C E C...` line
- multipla-escolha: `Questão 1 2 3...`/`Quest` line followed by a line of
  A-E/X letters

`X` means anulado. Auto-detects the format by which parse yields more pairs.
"""
import re
import subprocess
from pathlib import Path


def _layout_text(pdf_path):
    if str(pdf_path).endswith(".txt"):
        return Path(pdf_path).read_text()
    return subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                          capture_output=True, text=True).stdout


def parse_gabarito(pdf_path):
    txt = _layout_text(pdf_path)
    lines = txt.splitlines()
    gab = {}
    for i, l in enumerate(lines):
        if i + 1 >= len(lines):
            continue
        if re.match(r"\s*Item\b", l) and "Gabarito" in lines[i + 1]:
            nums = [int(x) for x in re.findall(r"\d+", l.split("Item", 1)[1])]
            vals = re.findall(r"\b[CEX]\b",
                              lines[i + 1].split("Gabarito", 1)[1])
            for n, v in zip(nums, vals):
                gab[n] = v
        elif re.match(r"\s*Quest", l):
            nums = [int(x) for x in re.findall(r"\d+", l)]
            vals = re.findall(r"[A-EX]\b", lines[i + 1])
            for n, v in zip(nums, vals):
                gab[n] = v
    return gab


def report(gab):
    """Human-readable one-line audit for a parsed gabarito."""
    if not gab:
        return "EMPTY"
    xs = sorted(n for n, v in gab.items() if v == "X")
    missing = [n for n in range(min(gab), max(gab) + 1) if n not in gab]
    return (f"{len(gab)} items ({min(gab)}-{max(gab)}) "
            f"anulados: {xs or '-'} faltando: {missing or '-'}")
