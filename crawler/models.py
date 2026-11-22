"""Pydantic schemas for operação papiro prova extraction (crawler-olavo).

Two layers:

- `ProvaExtraida` / `QuestaoExtraida`: the extraction schema passed to
  Firecrawl's `json` format — only what is printed on the prova page.
- `Questao`: the normalized dataset record stored in
  `data/questions/<EVENTO>.json` shards (see crawler/shards.py);
  job metadata (banca/orgao/cargo/ano/fonte) comes from `ProvaMeta`, not
  from the page.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, Optional

from pydantic import BaseModel, Field

TipoQuestao = Literal["certo_errado", "multipla_escolha"]


class QuestaoExtraida(BaseModel):
    """One question as printed on the prova — extraction-layer schema."""

    numero: int = Field(description="Número da questão na prova")
    enunciado: str = Field(
        description="Enunciado completo, incluindo texto-base e comando da questão"
    )
    alternativas: list[str] = Field(
        description="Alternativas em ordem; ['Certo', 'Errado'] para itens de certo/errado"
    )
    gabarito: Optional[str] = Field(
        default=None,
        description="Letra a-e ou 'certo'/'errado'; null quando a prova não traz gabarito",
    )


class ProvaExtraida(BaseModel):
    """Schema sent to Firecrawl `json` format via `model_json_schema()`."""

    questoes: list[QuestaoExtraida]


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", ascii_text.lower())).strip("-")


class ProvaMeta(BaseModel):
    """Job metadata for one prova — set by crawl config, never extracted."""

    banca: str
    orgao: str
    cargo: str
    ano: int
    fonte: str
    assunto: str = ""
    id_orgao: Optional[str] = None  # short slug for ids, e.g. "pf", "trt15"
    id_cargo: Optional[str] = None  # e.g. "escrivao"; defaults to first word


class Questao(BaseModel):
    """Dataset record — the flat shape shard_to_records() emits and the API serves."""

    id: str
    banca: str
    orgao: str
    cargo: str
    ano: int
    assunto: str
    tipo: TipoQuestao
    enunciado: str
    alternativas: list[str]
    gabarito: str
    fonte: str


def make_id(meta: ProvaMeta, numero: int) -> str:
    orgao = meta.id_orgao or slugify(meta.orgao)
    cargo = meta.id_cargo or slugify(meta.cargo.split()[0])
    return f"{slugify(meta.banca)}-{meta.ano}-{orgao}-{cargo}-{numero:03d}"


def infer_tipo(alternativas: list[str]) -> TipoQuestao:
    if len(alternativas) == 2 and {a.strip().lower() for a in alternativas} == {"certo", "errado"}:
        return "certo_errado"
    return "multipla_escolha"


def to_questao(
    extraida: QuestaoExtraida,
    meta: ProvaMeta,
    gabarito: Optional[str] = None,
) -> Questao:
    tipo = infer_tipo(extraida.alternativas)
    gab = (gabarito or extraida.gabarito or "").strip().lower()
    valid = {"certo", "errado"} if tipo == "certo_errado" else set("abcde")
    if gab not in valid:
        raise ValueError(
            f"Questão {extraida.numero}: gabarito {gab!r} inválido para {tipo} "
            "(extraia o gabarito em segunda passada)"
        )
    return Questao(
        id=make_id(meta, extraida.numero),
        banca=meta.banca,
        orgao=meta.orgao,
        cargo=meta.cargo,
        ano=meta.ano,
        assunto=meta.assunto,
        tipo=tipo,
        enunciado=extraida.enunciado,
        alternativas=extraida.alternativas,
        gabarito=gab,
        fonte=meta.fonte,
    )
