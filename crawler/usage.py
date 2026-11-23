"""Append credit-usage entries to FIRECRAWL_USAGE.md and refresh totals.

The "## Log" section must stay the last section of that file so rows can be
appended at EOF. The ledger path resolves to `$PAPIRO_LEDGER`, else the repo
`.agents/docs/FIRECRAWL_USAGE.md`, else `crawler/.cache/` — so in the Docker
image (no `.agents/`) calls still get logged into the cache volume instead of
crashing the extraction.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
_REPO_LEDGER = HERE.parent / ".agents" / "docs" / "FIRECRAWL_USAGE.md"
_FALLBACK_LEDGER = HERE / ".cache" / "FIRECRAWL_USAGE.md"


def ledger_path() -> Path:
    if p := os.environ.get("PAPIRO_LEDGER"):
        return Path(p)
    return _REPO_LEDGER if _REPO_LEDGER.exists() else _FALLBACK_LEDGER


LEDGER = ledger_path()
_ROW = re.compile(r"^\| *(\d{4}-\d{2}-\d{2}) *\|")


def log_call(
    task: str,
    tool: str,
    items: int | str,
    credits: int,
    notes: str = "",
    path: Path | None = None,
    day: date | None = None,
) -> None:
    path = path or ledger_path()
    day = day or date.today()
    # notes carrega URL derivada da banca — uma linha só, sem `|` cru
    notes = (notes.splitlines() or [""])[0].replace("|", "\\|")
    row = f"| {day.isoformat()} | {task} | {tool} | {items} | {credits} | {notes} |"
    try:
        text = path.read_text() if path.exists() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        text += row + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_refresh_totals(text))
    except OSError as exc:
        print(f"!! ledger não gravável ({path}): {exc} — linha: {row}",
              file=sys.stderr)


def _refresh_totals(text: str) -> str:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    all_time = week = 0
    for line in text.splitlines():
        if not _ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        try:
            d, c = date.fromisoformat(cells[0]), int(cells[4])
        except (ValueError, IndexError):
            continue
        all_time += c
        if d >= week_start:
            week += c
    text = re.sub(r"(\| *All time *\| *)\d+( *\|)", rf"\g<1>{all_time}\g<2>", text)
    text = re.sub(r"(\| *Current week *\| *)\d+( *\|)", rf"\g<1>{week}\g<2>", text)
    return text
