"""Política de seleção/ranqueamento Cebraspe — o que vale ingerir primeiro.

``PRIORIDADES`` ordena categorias BR casadas com ``norm("<eventoURL>
<eventoNomeAbreviado> <órgão>")``; ``ranquear`` é a ordem do ``next``
(ano desc, vagas desc). Vive no adapter: outra banca, outra política.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from . import api

# Categorias de prioridade, na ordem em que são processadas.
PRIORIDADES: dict[str, str] = {
    "tribunais": r"\bTRIBUNA|\b(TJ|TJDFT|TJM|TRF|TRT|TRE|STJ|STF|STM|TST|TSE|TCU|TCE|TCM|TC|CNJ|"
                 r"CPNUJE)\b|\b(TRF|TRT)\d",
    "policias": r"\bPOLICIA|\bPOLICIAL|\b(PF|PRF|PC|PM|PCDF|PJC|POLC|PP|PPF|DPF|DEPEN|SEAP|SSP|"
                r"CBM|CBMDF)\b|PENITENCI|BOMBEIRO",
    "inss": r"\bINSS\b|SEGURO SOCIAL",
    "bancos": r"\bBANCO\b|\b(BB|BCB|BACEN|CAIXA|CEF|BNB|BASA|BRB|BNDES|BDMG|BANRISUL|BANESE|"
              r"BANPARA)\b",
    # só reguladoras: agências nacionais e estaduais de regulação
    # (sem a sigla ANA solta: "ANA" também abrevia "Analista" nos nomes de evento)
    "agencias": r"AGENCIA NACIONAL|REGULACAO|REGULADORA|AGUAS E SANEAMENTO|"
                r"\b(ANAC|ANATEL|ANEEL|ANP|ANS|ANTAQ|ANTT|ANVISA|ANM|"
                r"ANCINE|ARSAL|ARSESP|ADASA|AGERGS|AGER|AGEPAR|ARCE|ARSAE)\b",
}


def tipo_caderno(descricao: str) -> Optional[int]:
    m = re.search(r"\bTIPO (\d+)\b", api.norm(descricao))
    return int(m.group(1)) if m else None


def parse_anos(texto: Optional[str]) -> Optional[set[int]]:
    """'2022-2026' → {2022,…,2026}; '2021,2023' → {2021, 2023}."""
    if not texto:
        return None
    anos: set[int] = set()
    for parte in texto.split(","):
        parte = parte.strip()
        m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", parte)
        if m:
            anos.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif parte:
            anos.add(int(parte))
    return anos


def categoria_de(e: dict, categorias: Iterable[str]) -> Optional[str]:
    texto = api.norm(f"{e.get('evento', '')} {e.get('evento_nome') or ''} {e.get('orgao', '')}")
    for c in categorias:
        if re.search(PRIORIDADES[c], texto):
            return c
    return None


def ranquear(eventos: Iterable[dict]) -> list[dict]:
    """Ordem do `next`: mais recentes e com mais vagas primeiro."""
    return sorted(eventos, key=lambda e: (-(e.get("eventoAno") or 0),
                                          -(int(e.get("eventoTotalVagas") or 0))))
