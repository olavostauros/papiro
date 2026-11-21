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
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import discover, gabarito as gabmod, usage
from .models import ProvaExtraida, ProvaMeta, Questao, QuestaoExtraida, to_questao
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
class Plano:
    """Decisão (grátis) de qual extrator gera cada item de uma prova."""
    gab: gabmod.Gabarito
    itens_local: Optional[dict[int, str]] = None
    firecrawl: Optional[str] = None          # None | "itens" | "prova"
    itens_fallback: list[int] = field(default_factory=list)
    motivo: str = ""


EXTRATORES = ("local", "firecrawl", "hibrido")


def planejar(e: dict, gab: gabmod.Gabarito, *, extrator: str,
             pdf_itens: Optional[PdfItens]) -> Plano:
    """local: só o extrator local. firecrawl: só Firecrawl. hibrido: local, com
    Firecrawl POR ITEM para fórmula ilegível e POR PROVA quando a cobertura não
    fecha com o gabarito (ou a prova não é certo/errado)."""
    from . import extract_local
    pl = Plano(gab=gab)
    if pdf_itens is not None:
        try:
            pl.itens_local = pdf_itens(e["url_prova"], gab.itens)
        except Exception as exc:  # noqa: BLE001
            pl.motivo = f"extrator local falhou: {type(exc).__name__}: {exc}"
    if extrator == "firecrawl":
        pl.firecrawl, pl.motivo = "prova", "--extrator firecrawl"
        return pl
    if gab.tipo != "certo_errado":
        pl.firecrawl, pl.motivo = "prova", "múltipla escolha (extrator local só faz certo/errado)"
        return pl
    if pl.itens_local is None:
        pl.firecrawl, pl.motivo = "prova", pl.motivo or "extrator local indisponível"
        return pl
    faltam = sorted(set(gab.itens) - set(pl.itens_local))
    if faltam:
        cob = 1 - len(faltam) / len(gab.itens)
        pl.firecrawl = "prova"
        pl.motivo = (f"cobertura local {cob:.0%} "
                     f"(faltam {faltam[:8]}{'…' if len(faltam) > 8 else ''})")
        return pl
    # fórmula ilegível só importa em item que vira registro (anulado não entra)
    ileg = [n for n in extract_local.ilegiveis(pl.itens_local) if n not in gab.anulados]
    if ileg:
        pl.firecrawl, pl.itens_fallback = "itens", ileg
        pl.motivo = f"fórmula ilegível nos itens {ileg}"
    return pl


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
    origem: dict[int, str] = field(default_factory=dict)  # item → local | firecrawl | omitido
    fallback: str = ""


def _firecrawl(e: dict, res: Resultado, *, extractor: Extractor, ledger: Path,
               estimativa: int) -> Optional[ProvaExtraida]:
    """Extração Firecrawl da prova inteira (cache → zero crédito)."""
    cpath = extracao_cache(e)
    if cpath.exists():
        res.cache = True
        return ProvaExtraida.model_validate_json(cpath.read_text(encoding="utf-8"))
    antes = total_ledger(ledger)
    try:
        prova = extractor(e["url_prova"], task_de(e))
    except Exception as exc:  # noqa: BLE001
        res.creditos = total_ledger(ledger) - antes
        res.status, res.mensagem = "erro", f"extração: {type(exc).__name__}: {exc}"
        return None
    res.creditos = total_ledger(ledger) - antes
    if res.creditos <= 0:
        # extract_prova só registra quando a resposta traz creditsUsed
        usage.log_call(task=task_de(e), tool="sdk:scrape[json]", items=1,
                       credits=estimativa, path=ledger,
                       notes=f"{e['url_prova']} - creditsUsed ausente; estimativa run.py")
        res.creditos = estimativa
        res.mensagem = "creditsUsed ausente na resposta: estimativa registrada no ledger"
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(prova.model_dump_json(indent=2), encoding="utf-8")
    return prova


def _da_local(itens: dict[int, str], numeros: Iterable[int]) -> list[QuestaoExtraida]:
    return [QuestaoExtraida(numero=n, enunciado=itens[n], alternativas=["Certo", "Errado"])
            for n in sorted(numeros) if n in itens]


def processar(e: dict, ds: Dataset, *, plano: Plano, extrator: str, extractor: Extractor,
              ledger: Path, estimativa: int) -> Resultado:
    res = Resultado(entrada=e, fallback=plano.motivo)
    gab = plano.gab
    omitidos: list[int] = []

    if plano.firecrawl is None:                         # 100% local, zero crédito
        prova = ProvaExtraida(questoes=_da_local(plano.itens_local, gab.itens))
        res.origem = {q.numero: "local" for q in prova.questoes}
    elif extrator == "local":                           # nunca gasta crédito
        if plano.firecrawl == "prova":
            res.status, res.mensagem = "erro", f"--extrator local: {plano.motivo}"
            return res
        omitidos = plano.itens_fallback                 # fórmula ilegível fica de fora
        prova = ProvaExtraida(questoes=_da_local(
            plano.itens_local, [n for n in gab.itens if n not in omitidos]))
        res.origem = {q.numero: "local" for q in prova.questoes}
        res.origem.update({n: "omitido (fórmula ilegível)" for n in omitidos})
    else:
        fc = _firecrawl(e, res, extractor=extractor, ledger=ledger, estimativa=estimativa)
        if fc is None:
            return res
        if plano.firecrawl == "prova":
            prova = fc
            res.origem = {q.numero: "firecrawl" for q in prova.questoes}
        else:                                           # por item: só as fórmulas
            do_fc = {q.numero: q for q in fc.questoes}
            questoes = _da_local(plano.itens_local,
                                 [n for n in gab.itens if n not in plano.itens_fallback])
            res.origem = {q.numero: "local" for q in questoes}
            for n in plano.itens_fallback:
                if n in do_fc:
                    questoes.append(QuestaoExtraida(numero=n, enunciado=do_fc[n].enunciado,
                                                    alternativas=["Certo", "Errado"]))
                    res.origem[n] = "firecrawl"
            prova = ProvaExtraida(questoes=sorted(questoes, key=lambda q: q.numero))

    # validação (+ cruzamento com o texto do PDF, grátis). Com itens omitidos, o
    # gabarito considerado é o dos itens que de fato entram.
    gab_val = gab if not omitidos else gabmod.Gabarito(
        respostas={n: r for n, r in gab.respostas.items() if n not in omitidos}, url=gab.url)
    rel = validar(prova, gab_val, caderno=f"{e['evento']}/{e['caderno']}",
                  url_prova=e["url_prova"], url_gabarito=e["url_gabarito"],
                  itens_pdf=plano.itens_local, so_indicativo=set(plano.itens_fallback))
    if plano.motivo and plano.firecrawl:
        rel.avisos.append(f"fallback Firecrawl ({plano.firecrawl}): {plano.motivo}")
    if omitidos:
        rel.avisos.append(f"--extrator local: itens com fórmula ilegível omitidos: {omitidos}")
    res.relatorio = rel
    if not rel.aprovada:
        res.status = "reprovada"
        return res

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


def custo_estimado(e: dict, plano: Plano, page_counter: PageCounter) -> int:
    """Créditos que esta prova vai gastar (0 se 100% local ou já em cache)."""
    if plano.firecrawl is None or extracao_cache(e).exists():
        return 0
    return page_counter(e["url_prova"]) + CUSTO_FIXO


def executar(manifesto: dict, ds: Dataset, *, limite: int, teto: int,
             extractor: Extractor, gab_loader: GabLoader, page_counter: PageCounter,
             ledger: Path = usage.LEDGER, eventos: Iterable[str] = (),
             cadernos: Iterable[str] = (), incluir_curso_formacao: bool = False,
             pdf_itens: Optional[PdfItens] = None, extrator: str = "hibrido",
             filtros: Optional[dict] = None, log=print) -> dict:
    cand, pul = selecionar(manifesto, ds, eventos=eventos, cadernos=cadernos,
                           incluir_curso_formacao=incluir_curso_formacao, **(filtros or {}))
    gasto = 0
    resultados: list[Resultado] = []
    parado = None
    for e in cand:
        if len(resultados) >= limite:
            break
        # gabarito e extrator local primeiro: grátis; se falharem, nada é gasto
        try:
            gab = gab_loader(e["url_gabarito"])
        except Exception as exc:  # noqa: BLE001
            resultados.append(Resultado(entrada=e, status="erro",
                                        mensagem=f"gabarito: {type(exc).__name__}: {exc}"))
            continue
        plano = planejar(e, gab, extrator=extrator, pdf_itens=pdf_itens)
        est = 0
        if extrator != "local":
            try:
                est = custo_estimado(e, plano, page_counter)
            except Exception as exc:  # noqa: BLE001
                resultados.append(Resultado(entrada=e, status="erro",
                                            mensagem=f"download da prova: {exc}"))
                continue
            if est and gasto + est > teto:
                parado = (f"teto de créditos: gasto {gasto} + estimativa {est} "
                          f"> {teto} ({e['caderno']})")
                log(f"PARANDO — {parado}")
                break
        modo = "local" if plano.firecrawl is None else f"firecrawl/{plano.firecrawl}"
        log(f"→ {e['evento']}/{e['caderno']} ({len(e['cargos'])} cargo(s), {modo}, "
            f"estimativa {est} créditos)")
        r = processar(e, ds, plano=plano, extrator=extrator, extractor=extractor,
                      ledger=ledger, estimativa=est)
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
        "extrator": extrator,
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
            "fallback": r.fallback,
            "itens_por_extrator": dict(Counter(r.origem.values())),
            "extrator_por_item": {str(n): o for n, o in sorted(r.origem.items())},
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
    ap.add_argument("--extrator", choices=EXTRATORES, default="hibrido",
                    help="local (zero crédito), firecrawl, ou hibrido (padrão: local + "
                         "Firecrawl por item p/ fórmula e por prova p/ cobertura incompleta)")
    ap.add_argument("--manifesto", type=Path, default=discover.MANIFEST)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    args = ap.parse_args(argv)

    if args.descobrir or not args.manifesto.exists():
        discover.salvar(discover.descobrir(discover.make_fetch()), args.manifesto)
    manifesto = json.loads(args.manifesto.read_text(encoding="utf-8"))
    ds = Dataset.carregar(args.dataset)

    if args.dry_run:
        return plano(manifesto, ds, args)

    if args.limite_provas is None or (args.teto_creditos is None and args.extrator != "local"):
        ap.error("--limite-provas (e --teto-creditos, exceto com --extrator local) são "
                 "obrigatórios fora do --dry-run")
    if args.extrator == "local":
        args.teto_creditos = 0

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
                   extrator=args.extrator, eventos=args.evento, cadernos=args.caderno,
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
