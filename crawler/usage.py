"""Append credit-usage entries to FIRECRAWL_USAGE.md and refresh totals.

The "## Log" section must stay the last section of that file so rows can be
appended at EOF.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

LEDGER = (Path(__file__).resolve().parent.parent
          / ".agents" / "docs" / "FIRECRAWL_USAGE.md")
_ROW = re.compile(r"^\| *(\d{4}-\d{2}-\d{2}) *\|")


def log_call(
    task: str,
    tool: str,
    items: int | str,
    credits: int,
    notes: str = "",
    path: Path = LEDGER,
    day: date | None = None,
) -> None:
    day = day or date.today()
    text = path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    text += f"| {day.isoformat()} | {task} | {tool} | {items} | {credits} | {notes} |\n"
    path.write_text(_refresh_totals(text))


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
