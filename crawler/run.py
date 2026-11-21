"""Pipeline Cebraspe ponta a ponta (CLI).

manifesto → pula o que já está no dataset → gabarito definitivo (grátis) →
``extract_prova`` (Firecrawl, créditos) → validação → append no dataset.

Exemplos::

    python -m crawler.run --dry-run                       # zero créditos
    python -m crawler.run --dry-run --evento TRF6_24
    python -m crawler.run --limite-provas 1 --teto-creditos 30 --caderno 945_ANAC_23_CB1_01

Controle de gasto:

- ``--teto-creditos N`` é obrigatório fora do ``--dry-run``. Antes de cada
  extração o custo é estimado (páginas do PDF + 4, padrão observado no lote
  PF 2025) e a execução PARA se ``gasto + estimativa > N``.
- O gasto real vem do ledger ``FIRECRAWL_USAGE.md`` (``extract_prova`` já
  registra via ``crawler/usage.py``). Se a resposta não trouxer
  ``creditsUsed`` e nada for registrado, o run registra a estimativa e avisa.
- Toda extração é salva em ``crawler/.cache/extracoes/`` antes de validar:
  re-execuções reaproveitam o JSON e não gastam crédito de novo.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import discover, gabarito as gabmod, usage
from .models import ProvaExtraida, ProvaMeta, Questao, to_questao
from .validate import Relatorio, formatar, validar

HERE = Path(__file__).resolve().parent
DATASET = discover.DATASET
EXTRACOES = HERE / ".cache" / "extracoes"
REPORTS = HERE / "reports"
CUSTO_FIXO = 4  # créditos de json-extraction por prova, além de 1/página

Extractor = Callable[[str, str], ProvaExtraida]          # (url, task) -> prova
GabLoader = Callable[[str], gabmod.Gabarito]             # url -> gabarito
PageCounter = Callable[[str], int]                       # url -> nº de páginas
PdfItens = Callable[[str, list[int]], dict[int, str]]    # url, itens -> texto por item


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

@dataclass
class Dataset:
    path: Path
    questoes: list[dict]
    ids: set[str] = field(default_factory=set)
    fontes: set[str] = field(default_factory=set)
    eventos_pasta: set[str] = field(default_factory=set)  # fonte = só a pasta do evento

    @classmethod
    def carregar(cls, path: Path = DATASET) -> "Dataset":
        qs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        ds = cls(path=path, questoes=qs)
        for q in qs:
            ds.ids.add(q["id"])
            f = q.get("fonte", "")
            ds.fontes.add(f.lower())
            m = re.search(r"/concursos/([^/]+)/(?:arquivos/?)?$", f)
            if m:
                ds.eventos_pasta.add(m.group(1).upper())
        return ds

    def ja_ingerida(self, entrada: dict) -> Optional[str]:
        if entrada["url_prova"].lower() in self.fontes:
            return "url da prova já é fonte no dataset"
        if entrada["evento"].upper() in self.eventos_pasta:
            return "evento já ingerido (fonte só com a pasta do evento)"
        return None

    def append(self, novas: list[Questao]) -> tuple[int, list[str]]:
        add, colisoes = 0, []
        for q in novas:
            if q.id in self.ids:
                colisoes.append(q.id)
                continue
            self.questoes.append(q.model_dump())
            self.ids.add(q.id)
            self.fontes.add(q.fonte.lower())
            add += 1
        return add, colisoes

    def salvar(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.questoes, ensure_ascii=False, indent=2))
        tmp.replace(self.path)


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def tipo_caderno(descricao: str) -> Optional[int]:
    m = re.search(r"\bTIPO (\d+)\b", discover.norm(descricao))
    return int(m.group(1)) if m else None


def selecionar(manifesto: dict, ds: Dataset, *, eventos: Iterable[str] = (),
               cadernos: Iterable[str] = (), incluir_curso_formacao: bool = False
               ) -> tuple[list[dict], list[dict]]:
    """Retorna (candidatas, puladas[{caderno, evento, motivo}])."""
    evs = {e.upper() for e in eventos}
    cads = {c.upper() for c in cadernos}
    cand, pul = [], []
    for e in manifesto["provas"]:
        def pula(motivo: str):
            pul.append({"evento": e["evento"], "caderno": e["caderno"], "motivo": motivo})
        if evs and e["evento"].upper() not in evs:
            continue
        if cads and e["caderno"].upper() not in cads:
            continue
        if not e.get("url_gabarito"):
            pula("sem gabarito definitivo"); continue
        if not e.get("cargos"):
            pula(e.get("cargo_como") or "cargo não identificado"); continue
        if e.get("fase") != "objetiva" and not incluir_curso_formacao:
            pula(f"fase {e.get('fase')}"); continue
        t = tipo_caderno(e.get("descricao", ""))
        if t is not None and t != 1:
            pula(f"caderno TIPO {t} (só o TIPO 1 é ingerido)"); continue
        motivo = ds.ja_ingerida(e)
        if motivo:
            pula(motivo); continue
        cand.append(e)
    # mais recentes primeiro; dentro do evento, ordem estável do manifesto
    cand.sort(key=lambda e: -(e.get("ano") or 0))
    return cand, pul


# ---------------------------------------------------------------------------
# Créditos
# ---------------------------------------------------------------------------

def total_ledger(path: Path = usage.LEDGER) -> int:
    if not path.exists():
        return 0
    # usage.py grava com o encoding padrão do sistema (cp1252 no Windows): lê tolerante
    texto = path.read_bytes().decode("utf-8", errors="replace")
    m = re.search(r"\| *All time *\| *(\d+) *\|", texto)
    return int(m.group(1)) if m else 0


def contar_paginas(url: str) -> int:
    pdf = gabmod.baixar(url)
    return max(1, gabmod.pdf_to_text(pdf).count("\f"))


def itens_do_pdf_url(url: str, esperados: list[int]) -> dict[int, str]:
    from . import extract_local
    return extract_local.itens_do_pdf(gabmod.baixar(url), esperados)


def task_de(e: dict) -> str:
    return f"cebraspe-{e.get('ano')}-{e.get('id_orgao')}-{e['caderno']}".lower()


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def extracao_cache(e: dict) -> Path:
    return EXTRACOES / e["evento"] / f"{e['caderno']}.json"


def montar_questoes(e: dict, prova: ProvaExtraida, gab: gabmod.Gabarito) -> list[Questao]:
    out = []
    for c in e["cargos"]:
        meta = ProvaMeta(banca="Cebraspe", orgao=e["orgao"], cargo=c["nome"],
                         ano=e["ano"], fonte=e["url_prova"], assunto=e.get("assunto") or "",
                         id_orgao=e.get("id_orgao"), id_cargo=c.get("id_cargo"))
        for q in prova.questoes:
            g = gab.para_dataset(q.numero)
            if g is None:  # anulado (X) → não vira registro
                continue
            out.append(to_questao(q, meta, gabarito=g))
    return out


@dataclass
class Resultado:
    entrada: dict
    relatorio: Optional[Relatorio] = None
    status: str = ""                 # aprovada | reprovada | erro | parado
    creditos: int = 0
    cache: bool = False
    adicionadas: int = 0
    colisoes: list[str] = field(default_factory=list)
    mensagem: str = ""


def processar(e: dict, ds: Dataset, *, extractor: Extractor, gab_loader: GabLoader,
              ledger: Path, estimativa: int,
              pdf_itens: Optional[PdfItens] = None) -> Resultado:
    res = Resultado(entrada=e)
    # 1) gabarito primeiro: é grátis e, se falhar, nenhum crédito é gasto
    try:
        gab = gab_loader(e["url_gabarito"])
    except Exception as exc:  # noqa: BLE001
        res.status, res.mensagem = "erro", f"gabarito: {type(exc).__name__}: {exc}"
        return res

    # 2) extração (cache → zero crédito)
    cpath = extracao_cache(e)
    if cpath.exists():
        prova = ProvaExtraida.model_validate_json(cpath.read_text(encoding="utf-8"))
        res.cache = True
    else:
        antes = total_ledger(ledger)
        try:
            prova = extractor(e["url_prova"], task_de(e))
        except Exception as exc:  # noqa: BLE001
            depois = total_ledger(ledger)
            res.creditos = depois - antes
            res.status, res.mensagem = "erro", f"extração: {type(exc).__name__}: {exc}"
            return res
        depois = total_ledger(ledger)
        res.creditos = depois - antes
        if res.creditos <= 0:
            # extract_prova só registra quando a resposta traz creditsUsed
            usage.log_call(task=task_de(e), tool="sdk:scrape[json]", items=1,
                           credits=estimativa, path=ledger,
                           notes=f"{e['url_prova']} - creditsUsed ausente; estimativa run.py")
            res.creditos = estimativa
            res.mensagem = "creditsUsed ausente na resposta: estimativa registrada no ledger"
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(prova.model_dump_json(indent=2), encoding="utf-8")

    # 3) validação (+ cruzamento com o texto do PDF, grátis)
    itens_pdf, aviso_pdf = None, None
    if pdf_itens is not None:
        try:
            itens_pdf = pdf_itens(e["url_prova"], gab.itens)
        except Exception as exc:  # noqa: BLE001
            aviso_pdf = f"cruzamento com o PDF falhou: {type(exc).__name__}: {exc}"
    rel = validar(prova, gab, caderno=f"{e['evento']}/{e['caderno']}",
                  url_prova=e["url_prova"], url_gabarito=e["url_gabarito"],
                  itens_pdf=itens_pdf)
    if aviso_pdf:
        rel.avisos.append(aviso_pdf)
    res.relatorio = rel
    if not rel.aprovada:
        res.status = "reprovada"
        return res

    # 4) append
    try:
        novas = montar_questoes(e, prova, gab)
    except ValueError as exc:
        rel.aprovada = False
        rel.erros.append(f"to_questao: {exc}")
        res.status = "reprovada"
        return res
    res.adicionadas, res.colisoes = ds.append(novas)
    res.status = "aprovada"
    return res


def executar(manifesto: dict, ds: Dataset, *, limite: int, teto: int,
             extractor: Extractor, gab_loader: GabLoader, page_counter: PageCounter,
             ledger: Path = usage.LEDGER, eventos: Iterable[str] = (),
             cadernos: Iterable[str] = (), incluir_curso_formacao: bool = False,
             pdf_itens: Optional[PdfItens] = None, log=print) -> dict:
    cand, pul = selecionar(manifesto, ds, eventos=eventos, cadernos=cadernos,
                           incluir_curso_formacao=incluir_curso_formacao)
    gasto = 0
    resultados: list[Resultado] = []
    parado = None
    for e in cand:
        if len(resultados) >= limite:
            break
        if not extracao_cache(e).exists():
            try:
                est = page_counter(e["url_prova"]) + CUSTO_FIXO
            except Exception as exc:  # noqa: BLE001
                resultados.append(Resultado(entrada=e, status="erro",
                                            mensagem=f"download da prova: {exc}"))
                continue
            if gasto + est > teto:
                parado = (f"teto de créditos: gasto {gasto} + estimativa {est} "
                          f"> {teto} ({e['caderno']})")
                log(f"PARANDO — {parado}")
                break
        else:
            est = 0
        log(f"→ {e['evento']}/{e['caderno']} ({len(e['cargos'])} cargo(s), "
            f"estimativa {est} créditos)")
        r = processar(e, ds, extractor=extractor, gab_loader=gab_loader,
                      ledger=ledger, estimativa=est, pdf_itens=pdf_itens)
        gasto += r.creditos
        resultados.append(r)
        if r.relatorio:
            log(formatar(r.relatorio))
        if r.mensagem:
            log(f"  {r.status}: {r.mensagem}")
        if r.status == "aprovada":
            log(f"  +{r.adicionadas} questões no dataset"
                + (f" ({len(r.colisoes)} ids já existentes ignorados)" if r.colisoes else ""))
        log(f"  créditos: {r.creditos}{' (cache)' if r.cache else ''} | acumulado {gasto}/{teto}")

    if any(r.adicionadas for r in resultados):
        ds.salvar()
    return {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "limite_provas": limite,
        "teto_creditos": teto,
        "creditos_gastos": gasto,
        "parado": parado,
        "candidatas": len(cand),
        "puladas": len(pul),
        "provas": [{
            "evento": r.entrada["evento"],
            "caderno": r.entrada["caderno"],
            "cargos": [c["nome"] for c in r.entrada["cargos"]],
            "status": r.status,
            "creditos": r.creditos,
            "cache": r.cache,
            "adicionadas": r.adicionadas,
            "colisoes": r.colisoes,
            "mensagem": r.mensagem,
            "validacao": r.relatorio.to_dict() if r.relatorio else None,
        } for r in resultados],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def plano(manifesto: dict, ds: Dataset, args) -> int:
    cand, pul = selecionar(manifesto, ds, eventos=args.evento, cadernos=args.caderno,
                           incluir_curso_formacao=args.incluir_curso_formacao)
    from collections import Counter
    print(f"manifesto: {manifesto['resumo']}")
    print(f"candidatas: {len(cand)} provas em {len({e['evento'] for e in cand})} eventos "
          f"| puladas: {len(pul)}")
    for motivo, n in Counter(p["motivo"] for p in pul).most_common(8):
        print(f"  pulada ({n}): {motivo}")
    print(f"próximas {min(args.limite_provas or 10, len(cand))} (dry-run, zero créditos):")
    for e in cand[: args.limite_provas or 10]:
        cs = ", ".join(c["nome"] for c in e["cargos"][:3])
        mais = f" +{len(e['cargos']) - 3}" if len(e["cargos"]) > 3 else ""
        cad = e["caderno"] if len(e["caderno"]) <= 28 else e["caderno"][:12] + "…"
        print(f"  {e['ano']} {e['evento']:<22} {cad:<28} {e['assunto'] or '-':<26} "
              f"{cs}{mais}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Pipeline Cebraspe: manifesto → dataset")
    ap.add_argument("--dry-run", action="store_true", help="só descoberta/plano, zero créditos")
    ap.add_argument("--limite-provas", type=int, default=None, help="máx. de provas a processar")
    ap.add_argument("--teto-creditos", type=int, default=None,
                    help="para antes de ultrapassar N créditos Firecrawl (obrigatório fora do dry-run)")
    ap.add_argument("--evento", action="append", default=[], help="filtra por eventoURL")
    ap.add_argument("--caderno", action="append", default=[], help="filtra por caderno")
    ap.add_argument("--descobrir", action="store_true", help="regera o manifesto antes (grátis)")
    ap.add_argument("--incluir-curso-formacao", action="store_true")
    ap.add_argument("--manifesto", type=Path, default=discover.MANIFEST)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    args = ap.parse_args(argv)

    if args.descobrir or not args.manifesto.exists():
        discover.salvar(discover.descobrir(discover.make_fetch()), args.manifesto)
    manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
    ds = Dataset.carregar(args.dataset)

    if args.dry_run:
        return plano(manifesto, ds, args)

    if args.teto_creditos is None or args.limite_provas is None:
        ap.error("--teto-creditos e --limite-provas são obrigatórios fora do --dry-run")

    app = None

    def extractor(url: str, task: str) -> ProvaExtraida:
        nonlocal app
        from .extract import extract_prova, make_app  # só importa/abre a chave se for gastar
        if app is None:
            app = make_app()
        return extract_prova(app, url, task=task)

    rep = executar(manifesto, ds, limite=args.limite_provas, teto=args.teto_creditos,
                   extractor=extractor, gab_loader=gabmod.carregar,
                   page_counter=contar_paginas, pdf_itens=itens_do_pdf_url,
                   eventos=args.evento, cadernos=args.caderno,
                   incluir_curso_formacao=args.incluir_curso_formacao)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"run-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(p["status"] == "aprovada" for p in rep["provas"])
    print(f"\nresumo: {ok}/{len(rep['provas'])} aprovadas | créditos {rep['creditos_gastos']}"
          f"/{rep['teto_creditos']} | relatório: {out}")
    return 0 if all(p["status"] == "aprovada" for p in rep["provas"]) else 1


if __name__ == "__main__":
    sys.exit(main())
