"""Script local (fora da API pública) para aquecer o cache de ``/agente/explicar``.

Uso:
    python scripts/aquecer_cache_agente.py cebraspe-2024-pf-escrivao-001 cebraspe-2024-pf-escrivao-002
    python scripts/aquecer_cache_agente.py --arquivo ids.txt --url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Optional

import httpx


@dataclass
class WarmupResult:
    questao_id: str
    ok: bool
    status_code: int
    cached: Optional[bool] = None
    modelo: Optional[str] = None
    elapsed_ms: int = 0
    erro: str = ""


def carregar_ids(ids: Iterable[str], arquivo: Optional[Path] = None) -> list[str]:
    """Combina IDs da linha de comando e de arquivo, preservando ordem sem duplicar."""
    brutos: list[str] = list(ids)
    if arquivo is not None:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            limpa = linha.strip()
            if limpa and not limpa.startswith("#"):
                brutos.append(limpa)

    unicos: list[str] = []
    vistos: set[str] = set()
    for qid in brutos:
        limpo = qid.strip()
        if limpo and limpo not in vistos:
            vistos.add(limpo)
            unicos.append(limpo)
    return unicos


def aquecer_cache(
    ids: Iterable[str],
    *,
    base_url: str = "http://127.0.0.1:8000",
    intervalo: float = 1.5,
    timeout: float = 35.0,
    client: Optional[Any] = None,
) -> list[WarmupResult]:
    """Chama ``POST /agente/explicar`` para cada ``questao_id`` informado."""
    lista = carregar_ids(ids)
    endpoint = f"{base_url.rstrip('/')}/agente/explicar"
    resultados: list[WarmupResult] = []

    own_client = client is None
    sess = httpx.Client(timeout=timeout) if own_client else client
    try:
        for i, qid in enumerate(lista):
            t0 = time.perf_counter()
            try:
                resp = sess.post(endpoint, json={"questao_id": qid})
                ms = int((time.perf_counter() - t0) * 1000)
            except httpx.HTTPError as exc:
                ms = int((time.perf_counter() - t0) * 1000)
                resultados.append(
                    WarmupResult(
                        questao_id=qid,
                        ok=False,
                        status_code=0,
                        elapsed_ms=ms,
                        erro=type(exc).__name__,
                    )
                )
                continue

            if resp.status_code == 200:
                body = resp.json()
                resultados.append(
                    WarmupResult(
                        questao_id=qid,
                        ok=True,
                        status_code=200,
                        cached=bool(body.get("cached")),
                        modelo=body.get("modelo"),
                        elapsed_ms=ms,
                    )
                )
                if not body.get("cached") and intervalo > 0 and i < len(lista) - 1:
                    time.sleep(intervalo)
            else:
                resultados.append(
                    WarmupResult(
                        questao_id=qid,
                        ok=False,
                        status_code=resp.status_code,
                        elapsed_ms=ms,
                        erro=resp.text[:200],
                    )
                )
    finally:
        if own_client:
            sess.close()

    return resultados


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pré-aquece o cache em memória de POST /agente/explicar."
    )
    parser.add_argument("ids", nargs="*", help="IDs de questões a aquecer")
    parser.add_argument(
        "-f", "--arquivo", type=Path, help="Arquivo texto com 1 questao_id por linha"
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="URL base da API (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=1.5,
        help="Pausa em segundos entre chamadas não cacheadas (default: 1.5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=35.0,
        help="Timeout HTTP por requisição em segundos (default: 35)",
    )
    args = parser.parse_args(argv)

    lista = carregar_ids(args.ids, args.arquivo)
    if not lista:
        parser.error("Informe ao menos um questao_id ou --arquivo.")

    resultados = aquecer_cache(
        lista,
        base_url=args.url,
        intervalo=args.intervalo,
        timeout=args.timeout,
    )
    ok_count = sum(1 for r in resultados if r.ok)
    for r in resultados:
        if r.ok:
            print(
                f"[OK] {r.questao_id} | modelo={r.modelo} | cached={r.cached} | {r.elapsed_ms}ms"
            )
        else:
            print(
                f"[ERRO] {r.questao_id} | status={r.status_code} | {r.elapsed_ms}ms | {r.erro}"
            )
    print(f"\nResumo: {ok_count}/{len(resultados)} aquecidas com sucesso.")
    return 0 if ok_count == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
