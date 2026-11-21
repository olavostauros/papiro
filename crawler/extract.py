"""Structured prova extraction via Firecrawl `json` format (crawler-olavo)."""

from __future__ import annotations

from pathlib import Path

from firecrawl import Firecrawl

from .models import ProvaExtraida
from .usage import log_call

PROMPT = (
    "Extraia todas as questões da prova: número, enunciado completo "
    "(incluindo texto-base e comando) e alternativas em ordem."
)

ROOT = Path(__file__).resolve().parent.parent


def make_app() -> Firecrawl:
    key = (ROOT / ".env" / "FIRECRAWL_API_KEY").read_text().strip()
    return Firecrawl(api_key=key)


def _credits(result) -> int | None:
    meta = getattr(result, "metadata", None)
    if isinstance(meta, dict):
        return meta.get("creditsUsed") or meta.get("credits_used")
    return getattr(meta, "creditsUsed", None) or getattr(meta, "credits_used", None)


def extract_prova(app: Firecrawl, url: str, *, task: str) -> ProvaExtraida:
    result = app.scrape(
        url,
        formats=[{
            "type": "json",
            "schema": ProvaExtraida.model_json_schema(),
            "prompt": PROMPT,
        }],
    )
    credits = _credits(result)
    if credits:
        log_call(task=task, tool="sdk:scrape[json]", items=1, credits=credits, notes=url)
    return ProvaExtraida.model_validate(result.json)
