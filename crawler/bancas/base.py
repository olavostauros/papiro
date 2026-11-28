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
from typing import Any, Iterable, Optional, Protocol
import re
import unicodedata

from .. import gabarito as gabmod
from ..gabarito import Gabarito

# numero → item parseado. MC pode trazer assunto/blocos por item.
ParsedItens = dict[int, dict[str, Any]]   # {"enunciado", "alternativas", "assunto"}
Dropped = list[tuple]                     # linhas descartadas (auditoria)


# ---------------------------------------------------------------------------
# Defaults do pipeline manifesto→dataset
# ---------------------------------------------------------------------------

def norm(text: str) -> str:
    """Maiúsculas, sem acentos, pontuação vira espaço, espaços colapsados."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Z0-9]+", " ", t.upper())
    return re.sub(r"\s+", " ", t).strip()


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


def tipo_caderno(descricao: str) -> Optional[int]:
    """Número do tipo de caderno ("… TIPO 3") ou None quando não nominado."""
    m = re.search(r"\bTIPO (\d+)\b", norm(descricao))
    return int(m.group(1)) if m else None


class IngestDefaults:
    """Implementações default dos hooks que ``crawler.ingest`` consome.

    Adapters concretos podem herdar daqui (ou simplesmente expor os mesmos
    atributos — o pipeline é duck-typed). O default é conservador: sem
    categorias de prioridade, sem motor secundário ``pdftotext`` e sem
    fórmulas ilegíveis detectadas.
    """

    PRIORIDADES: dict[str, str] = {}
    itens_pdf = None
    mc_pdf = None
    assunto_por_item = False
    prova_variants = ("modern", "old")

    norm = staticmethod(norm)
    parse_anos = staticmethod(parse_anos)
    tipo_caderno = staticmethod(tipo_caderno)
    carregar_gabarito = staticmethod(gabmod.carregar)

    @staticmethod
    def categoria_de(e: dict, categorias: Iterable[str]) -> Optional[str]:
        return None

    @staticmethod
    def ilegiveis(itens: dict[int, str]) -> list[int]:
        return []

    @staticmethod
    def ilegiveis_mc(itens: dict[int, tuple]) -> list[int]:
        return []

    @staticmethod
    def chave_prova(fonte_ou_nome: str) -> str:
        """Chave conservadora: basename sem extensão (URLs perdem query/fragmento)."""
        nome = str(fonte_ou_nome).split("?", 1)[0].split("#", 1)[0]
        return Path(nome).stem


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

    # -- ingest manifesto→dataset -------------------------------------------
    # Hooks consumidos por ``crawler.ingest``; ``IngestDefaults`` tem a
    # implementação compartilhada da maioria. ``MANIFEST`` é um Path e
    # ``regen_manifest(path)`` regenera o manifesto da banca.
    MANIFEST: Path
    PRIORIDADES: dict[str, str]

    def regen_manifest(self, path: Path) -> dict:
        """Regenera ``crawler/manifests/<banca>.json`` a partir da fonte."""
        ...

    def carregar_gabarito(self, url: str) -> Gabarito:
        """URL de gabarito do manifesto → Gabarito definitivo."""
        ...

    def chave_prova(self, fonte_ou_nome: str) -> str:
        """Chave estável do caderno para deduplicar revisões do arquivo."""
        ...

    # -- job ----------------------------------------------------------------
    def fonte_url(self, evento: str, arquivo: str) -> str:
        """URL pública do arquivo — vira ``fonte`` dos registros."""
        ...

    def draft_job(self, detalhe: dict, manifest: dict[str, str],
                  workdir: Path) -> dict:
        """Rascunho de job.json a partir do detalhe + {nomeArquivo: local}."""
        ...
