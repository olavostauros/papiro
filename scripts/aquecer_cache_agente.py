"""Script local (fora da API pública) para aquecer o cache de ``/agente/explicar``.

Uso:
    python scripts/aquecer_cache_agente.py cebraspe-2024-pf-escrivao-001 cebraspe-2024-pf-escrivao-002
    python scripts/aquecer_cache_agente.py --resposta certo cebraspe-2022-inss-tecnico-seguro-social-112
    python scripts/aquecer_cache_agente.py cebraspe-2022-inss-tecnico-seguro-social-112:certo
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
    resposta_usuario: Optional[str] = None
    cached: Optional[bool] = None
    modelo: Optional[str] = None
    elapsed_ms: int = 0
    erro: str = ""


def _parse_item(
    item: str | tuple[str, Optional[str]], default_resposta: Optional[str] = None
) -> tuple[str, Optional[str]]:
    if isinstance(item, tuple):
        qid = item[0].strip()
        resp = item[1].strip().lower() if item[1] and item[1].strip() else None
        if resp is None and default_resposta:
            resp = default_resposta.strip().lower()
        return qid, resp or None

    raw = item.strip()
    if not raw:
        return "", None
    if ":" in raw:
        qid_part, resp_part = raw.split(":", 1)
        resp = resp_part.strip().lower() or None
        return qid_part.strip(), resp
    parts = raw.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip().lower() or None
    resp_def = default_resposta.strip().lower() if default_resposta and default_resposta.strip() else None
    return parts[0].strip(), resp_def


def carregar_ids(ids: Iterable[str], arquivo: Optional[Path] = None) -> list[str]:
    """Combina IDs da linha de comando e de arquivo, preservando ordem sem duplicar."""
    return [qid for qid, _ in carregar_itens(ids, arquivo)]


def carregar_itens(
    ids: Iterable[str | tuple[str, Optional[str]]],
    arquivo: Optional[Path] = None,
    resposta_default: Optional[str] = None,
) -> list[tuple[str, Optional[str]]]:
    """Combina itens ``(questao_id, resposta_usuario)`` sem duplicar."""
    brutos: list[str | tuple[str, Optional[str]]] = list(ids)
    if arquivo is not None:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            limpa = linha.strip()
            if limpa and not limpa.startswith("#"):
                brutos.append(limpa)

    unicos: list[tuple[str, Optional[str]]] = []
    vistos: set[tuple[str, Optional[str]]] = set()
    for bruto in brutos:
        qid, resp = _parse_item(bruto, resposta_default)
        if qid and (qid, resp) not in vistos:
            vistos.add((qid, resp))
            unicos.append((qid, resp))
    return unicos


def aquecer_cache(
    ids: Iterable[str | tuple[str, Optional[str]]],
    *,
    resposta_usuario: Optional[str] = None,
    base_url: str = "http://127.0.0.1:8000",
    intervalo: float = 1.5,
    timeout: float = 35.0,
    client: Optional[Any] = None,
) -> list[WarmupResult]:
    """Chama ``POST /agente/explicar`` para cada par ``(questao_id, resposta_usuario)``."""
    lista = carregar_itens(ids, resposta_default=resposta_usuario)
    endpoint = f"{base_url.rstrip('/')}/agente/explicar"
    resultados: list[WarmupResult] = []

    own_client = client is None
    sess = httpx.Client(timeout=timeout) if own_client else client
    try:
        for i, (qid, resp_sim) in enumerate(lista):
            payload: dict[str, Any] = {"questao_id": qid}
            if resp_sim is not None:
                payload["resposta_usuario"] = resp_sim
            t0 = time.perf_counter()
            try:
                resp = sess.post(endpoint, json=payload)
                ms = int((time.perf_counter() - t0) * 1000)
            except httpx.HTTPError as exc:
                ms = int((time.perf_counter() - t0) * 1000)
                resultados.append(
                    WarmupResult(
                        questao_id=qid,
                        ok=False,
                        status_code=0,
                        resposta_usuario=resp_sim,
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
                        resposta_usuario=resp_sim,
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
                        resposta_usuario=resp_sim,
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
    parser.add_argument(
        "ids",
        nargs="*",
        help="IDs de questões (ou 'id:resposta', ex.: cebraspe-...-112:certo)",
    )
    parser.add_argument(
        "-f",
        "--arquivo",
        type=Path,
        help="Arquivo texto com 1 questao_id (ou 'id:resposta') por linha",
    )
    parser.add_argument(
        "-r",
        "--resposta",
        default=None,
        help="Resposta simulada padrão ('certo'/'errado' ou 'a'..'e') quando não informada no item",
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

    lista = carregar_itens(args.ids, args.arquivo, resposta_default=args.resposta)
    if not lista:
        parser.error("Informe ao menos um questao_id ou --arquivo.")

    resultados = aquecer_cache(
        lista,
        resposta_usuario=args.resposta,
        base_url=args.url,
        intervalo=args.intervalo,
        timeout=args.timeout,
    )
    ok_count = sum(1 for r in resultados if r.ok)
    for r in resultados:
        resp_tag = f" | resposta={r.resposta_usuario}" if r.resposta_usuario else ""
        if r.ok:
            print(
                f"[OK] {r.questao_id}{resp_tag} | modelo={r.modelo} | cached={r.cached} | {r.elapsed_ms}ms"
            )
        else:
            print(
                f"[ERRO] {r.questao_id}{resp_tag} | status={r.status_code} | {r.elapsed_ms}ms | {r.erro}"
            )
    print(f"\nResumo: {ok_count}/{len(resultados)} aquecidas com sucesso.")
    return 0 if ok_count == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
