"""Utilitários do shape de manifesto consumido por ``crawler.ingest``.

Cada adapter monta as linhas ``provas`` no formato documentado em
``AGENTS.md``/``crawler.ingest``; este módulo só centraliza o resumo e a
gravação para que FCC/FGV emitam exatamente as mesmas chaves da Cebraspe.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def montar(fonte: str, eventos_listados: int, provas: list[dict],
           nao_mapeados: list[dict], falhas: list[dict],
           eventos_sem_provas: list[str]) -> dict:
    completas = [p for p in provas if p.get("url_gabarito") and p.get("cargos")]
    cargos = {(p["evento"], c.get("numero")) for p in completas for c in p["cargos"]}
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": fonte,
        "resumo": {
            "eventos_listados": eventos_listados,
            "eventos_com_provas": len({p["evento"] for p in provas}),
            "eventos_sem_provas": len(eventos_sem_provas),
            "eventos_com_falha": len(falhas),
            "provas": len(provas),
            "provas_completas": len(completas),
            "provas_objetivas_completas": sum(p.get("fase") == "objetiva" for p in completas),
            "cargos_distintos": len(cargos),
            "nao_mapeados": len(nao_mapeados),
        },
        "provas": provas,
        "nao_mapeados": nao_mapeados,
        "falhas": falhas,
        "eventos_sem_provas": eventos_sem_provas,
    }


def salvar(manifesto: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
