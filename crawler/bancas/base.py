"""Contrato de banca: o que o pipeline genérico precisa de cada adapter.

Um adapter encapsula tudo que é específico da banca — a API/URLs, a
classificação dos arquivos do evento, o parser de prova e o rascunho de
``job.json``. O motor (``crawler/pipeline.py``) resolve o adapter pelo
``job["banca"]`` e não conhece Cebraspe/FCC/FGV.

O ``job.json`` é a unidade de curadoria::

    {
      "banca": "cebraspe",                  # nome do adapter (registry)
      "evento": "BANRISUL_25",              # stem do shard <EVENTO>.json
      "workdir": "/tmp/banrisul_25",
      "meta": {"banca": "Cebraspe", "orgao": "...", "ano": 2025,
               "id_orgao": "banrisul"},
      "cargos": [{"cargo": "...", "id_cargo": "...",
                  "provas": [{"key": "CB1", "prova": "pro_CB1.pdf",
                              "gabarito": "gab_CB1.pdf", "tipo": "mc",
                              "arquivo": "077_BANRISUL_CB1_01.pdf"}]}],
      "unmatched": [],                      # provas sem cargo resolvido
      "variant": "modern",                  # repassado a parse_prova
      "skip": {"CB1": [16, 26]},            # itens ilegíveis (figuras etc.)
      "patch": {"CB1": {"36": "..."}}       # enunciados reconstruídos à mão
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..gabarito import Gabarito

# numero → item parseado. MC pode trazer assunto/blocos por item.
ParsedItens = dict[int, dict[str, Any]]   # {"enunciado", "alternativas", "assunto"}
Dropped = list[tuple]                     # linhas descartadas (auditoria)


class BancaAdapter(Protocol):
    """Interface que cada banca implementa (duck-typed, não precisa herdar)."""

    name: str                             # "cebraspe" → ids/shards/job["banca"]

    # -- descoberta (job-driven) -------------------------------------------
    def list_eventos(self) -> list[dict]:
        """Eventos disponíveis na fonte (para `next` ranquear)."""
        ...

    def get_evento(self, ref) -> dict:
        """Detalhe do evento: cargos + arquivos (provas/gabaritos)."""
        ...

    def arquivo_kind(self, arq: dict) -> str:
        """Classifica um arquivo do evento: 'prova' | 'gabarito' | 'outro'."""
        ...

    def arquivo_cargos(self, arq: dict) -> list[str]:
        """Cargos/áreas que a descrição do arquivo referencia."""
        ...

    # -- download -----------------------------------------------------------
    def download(self, evento: str, nome_arquivo: str, dest: Path) -> Path:
        """Baixa um arquivo do evento para ``dest``."""
        ...

    def fetch(self, detalhe: dict, workdir: Path, log=print) -> dict[str, str]:
        """Baixa provas+gabaritos do evento → ``{nomeArquivo: nome local}``."""
        ...

    # -- parsing ------------------------------------------------------------
    def parse_prova(self, pdf: Path, *, tipo: str, variant: str = "modern",
                    audit: bool = False) -> Any:
        """PDF da prova → ParsedItens; com audit=True → (itens, dropped)."""
        ...

    def parse_gabarito(self, pdf: Path) -> Gabarito:
        """PDF do gabarito → Gabarito."""
        ...

    # -- job ----------------------------------------------------------------
    def fonte_url(self, evento: str, arquivo: str) -> str:
        """URL pública do arquivo — vira ``fonte`` dos registros."""
        ...

    def draft_job(self, detalhe: dict, manifest: dict[str, str],
                  workdir: Path) -> dict:
        """Rascunho de job.json a partir do detalhe + {nomeArquivo: local}."""
        ...
