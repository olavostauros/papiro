#!/usr/bin/env python3
"""Repara o shard legado ABIN_17.

O shard original marcou todos os registros com a fonte-dir do evento e
concentrou as provas básicas compartilhadas em cargos genéricos inexistentes
no edital. Este script reatribui cada registro ao PDF oficial, expande as
provas básicas para os cargos/áreas reais (convenção atual do pipeline) e
corrige os gabaritos da trilha em espanhol — os enunciados preservados são
em espanhol, mas o lote legado usou a coluna amarela/inglesa do gabarito.

A saída canônica tem 2.155 registros: além da reconciliação de fontes,
cargos e gabaritos, o script reincorpora 18 itens não anulados ausentes do
lote legado, transcritos dos PDFs oficiais e marcados com texto-base de
imagem porque dependem de figura/circuito. A transcrição lineariza a
notação matemática em texto plano usando subscritos com ``_`` (por exemplo,
``R_1``, ``v_o(t)``, ``f_c``); no item 78, ``h_fe`` representa o parâmetro
com sobrelinha do PDF. O script é idempotente: um shard já canônico é
validado e reemitido sem nova transformação; ``--input`` permite aplicar a
transformação a uma cópia exportada do shard legado. Dry-run por padrão;
``--write`` regrava data/questions/ABIN_17.json.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.shards import load_shard_records, write_shard  # noqa: E402

EVENTO = "ABIN_17"
SHARD = ROOT / "data" / "questions" / f"{EVENTO}.json"
CDN = f"https://cdn.cebraspe.org.br/concursos/{EVENTO}/arquivos"
FONTE_DIR = f"{CDN}/"

CB1 = f"{CDN}/378_ABIN_CB1_01.PDF"
CB2 = f"{CDN}/378_ABIN_CB2_01.PDF"
CB3 = f"{CDN}/378_ABIN_CB3_01.PDF"
AGENTE_ESP = f"{CDN}/378_ABIN_015_01.PDF"

OFICIAL = "Oficial de Inteligência"
TECNICO = "Oficial Técnico de Inteligência"
AGENTE = "Agente de Inteligência"

CB2_ESPANHOL = {
    1: "errado", 2: "certo", 3: "errado", 4: "errado", 5: "certo",
    6: "certo", 7: None, 8: "errado", 9: "certo", 10: "certo",
}
CB3_ESPANHOL = {
    1: "errado", 2: "certo", 3: "certo", 4: "errado", 5: "errado",
}

FALTANTES_NAO_ANULADOS = {
    "378_ABIN_004_01.PDF": [109],
    "378_ABIN_009_01.PDF": [66, 67, 90],
    "378_ABIN_010_01.PDF": list(range(70, 81)),
    "378_ABIN_CB3_01.PDF": [45, 46, 47],
}


def _texto_imagem(conteudo: str) -> dict:
    return {"ref": "", "conteudo": conteudo, "citacao": "", "imagem": True}


TEXTO_004_109 = _texto_imagem(
    "Acerca de testes de penetração, julgue os itens seguintes.")
TEXTO_009_ELETRICA = _texto_imagem(
    "A figura abaixo mostra parte da instalação elétrica de um cômodo de "
    "apartamento.\n\nNessa figura, alguns elementos são identificados por "
    "números de ① a ⑤. Com referência a essa figura, julgue os itens que "
    "se seguem.")
TEXTO_009_HIDRO = _texto_imagem(
    "Considerando os hidrogramas A e B representados na figura precedente, "
    "julgue os itens subsequentes, acerca de hidrologia aplicada.")
TEXTO_010_THEVENIN = _texto_imagem(
    "Considere que todos os componentes do circuito precedente sejam ideais "
    "e que E_1 = 10 V, E_2 = 2 V, R_1 = R_2 = 4 kΩ, R_3 = R_4 = 2 kΩ. Com "
    "relação a esse circuito, julgue os itens seguintes.")
TEXTO_010_RC = _texto_imagem(
    "No circuito anterior, em que todos os componentes são considerados "
    "ideais, as transformadas de Laplace das tensões de entrada e de saída "
    "do circuito, v_i(t) e v_o(t), respectivamente, são dadas por V_i(s) e "
    "V_o(s). Acerca desse circuito, julgue os próximos itens.")
TEXTO_010_FONTE = _texto_imagem(
    "Considere que, no circuito precedente, que representa uma fonte de "
    "alimentação não regulada, os componentes sejam componentes típicos "
    "para esse tipo de fonte. Considere também que o valor do capacitor "
    "seja de 2.000 microfarads, que R_L = 100 ohms e que a tensão RMS no "
    "secundário seja de 12 volts RMS. Com relação a esse circuito, julgue "
    "os itens a seguir.")
TEXTO_010_AMPLIF = _texto_imagem(
    "Considere que o amplificador a transistor bipolar ilustrado "
    "anteriormente esteja polarizado na região ativa. Com relação a esse "
    "circuito, julgue os itens a seguir.")
TEXTO_CB3_FIGURAS = _texto_imagem(
    "As três figuras precedentes, cada uma com diversos símbolos, foram "
    "desenhadas na parede de um suposto esconderijo inimigo. O serviço de "
    "inteligência descobriu que cada um dos símbolos representa um "
    "algarismo do conjunto {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}.\n\n"
    "Com referência a essas figuras, julgue os itens seguintes.")

AREA4 = "Oficial de Inteligência - Área 4"
AREA5 = "Oficial Técnico de Inteligência - Área 5"
AREA6 = "Oficial Técnico de Inteligência - Área 6"

FALTANTES_CURADOS = [
    {
        "arquivo": "378_ABIN_004_01.PDF", "cargo": AREA4, "numero": 109,
        "gabarito": "errado", "texto": TEXTO_004_109,
        "enunciado": (
            "Na situação apresentada na figura a seguir, de acordo com o "
            "OSSTMM (The Open Source Security Testing Methodology Manual), "
            "seria correto classificar o teste de penetração como um teste "
            "do tipo tandem, mas não como um teste double blind, haja "
            "vista que, na técnica tandem, o alvo não recebe notificação "
            "prévia referente ao alcance da auditoria, aos canais testados "
            "e aos vetores de teste."),
    },
    {
        "arquivo": "378_ABIN_009_01.PDF", "cargo": AREA5, "numero": 66,
        "gabarito": "errado", "texto": TEXTO_009_ELETRICA,
        "enunciado": "O eletroduto indicado por ④ possui três neutros.",
    },
    {
        "arquivo": "378_ABIN_009_01.PDF", "cargo": AREA5, "numero": 67,
        "gabarito": "certo", "texto": TEXTO_009_ELETRICA,
        "enunciado": "O elemento indicado por ⑤ representa uma tomada baixa.",
    },
    {
        "arquivo": "378_ABIN_009_01.PDF", "cargo": AREA5, "numero": 90,
        "gabarito": "errado", "texto": TEXTO_009_HIDRO,
        "enunciado": (
            "Nos hidrogramas A e B, o ponto de inflexão após o ponto "
            "máximo caracteriza o fim do escoamento subterrâneo e o início "
            "do escoamento superficial."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 70,
        "gabarito": "certo", "texto": TEXTO_010_THEVENIN,
        "enunciado": (
            "O modelo de Thévenin equivalente ao circuito que se encontra "
            "à esquerda dos pontos A e B, ou seja, o circuito obtido pela "
            "retirada do resistor R_4 e da fonte E_2, é formado por uma "
            "fonte equivalente de Thévenin com tensão de 5 V em série com "
            "uma resistência equivalente de Thévenin de 4 kΩ."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 71,
        "gabarito": "errado", "texto": TEXTO_010_THEVENIN,
        "enunciado": (
            "O modelo de Norton equivalente ao circuito que se encontra "
            "à esquerda dos pontos A e B, ou seja, o circuito obtido pela "
            "retirada do resistor R_4 e da fonte E_2, é formado por uma "
            "fonte de corrente equivalente de Norton com corrente de "
            "1,2 mA em paralelo com uma resistência equivalente de Norton "
            "de 4 kΩ."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 72,
        "gabarito": "certo", "texto": TEXTO_010_THEVENIN,
        "enunciado": "A corrente I_2 é igual a 0,5 mA.",
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 73,
        "gabarito": "errado", "texto": TEXTO_010_THEVENIN,
        "enunciado": (
            "Nesse circuito, a lei de Kirchoff aplicada na malha mais à "
            "esquerda, na qual passa a corrente I_1, e que contêm a fonte "
            "E_1 e os resistores R_1 e R_2, é a seguinte: "
            "E_1 + R_1 I_1 + R_2(I_1 + I_2) = 0."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 74,
        "gabarito": "certo", "texto": TEXTO_010_RC,
        "enunciado": (
            "A função de transferência H(s) = V_o(s)/V_i(s), no domínio da "
            "transformada de Laplace, é representada pela expressão a "
            "seguir, em que R é um resistor e C um capacitor. "
            "H(s) = 1/(1 + sRC)."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 75,
        "gabarito": "certo", "texto": TEXTO_010_RC,
        "enunciado": (
            "O circuito mostrado pode funcionar como um filtro passa "
            "baixa, com frequência de corte, em Hz, dada por "
            "f_c = 1/(2πRC)."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 76,
        "gabarito": "errado", "texto": TEXTO_010_FONTE,
        "enunciado": (
            "Caso a resistência de carga seja reduzida de 100 ohms para "
            "50 ohms, a tensão de ondulação na tensão de saída irá se "
            "reduzir à metade."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 77,
        "gabarito": "errado", "texto": TEXTO_010_FONTE,
        "enunciado": (
            "A tensão média sobre o resistor de carga R_L é menor do que "
            "12 volts."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 78,
        "gabarito": "errado", "texto": TEXTO_010_AMPLIF,
        "enunciado": (
            "Caso ocorra um aumento de 5% no valor de R_C, sem que haja "
            "grande mudança na polarização do circuito ou no parâmetro "
            "h_fe, ocorrerá, em consequência, uma diminuição no ganho de "
            "tensão do amplificar."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 79,
        "gabarito": "errado", "texto": TEXTO_010_AMPLIF,
        "enunciado": (
            "Caso o capacitor C_3 seja retirado do circuito, ocorrerá uma "
            "mudança nas correntes de polarização do transistor, "
            "acompanhada de um aumento no ganho de tensão do circuito."),
    },
    {
        "arquivo": "378_ABIN_010_01.PDF", "cargo": AREA6, "numero": 80,
        "gabarito": "certo", "texto": TEXTO_010_AMPLIF,
        "enunciado": (
            "O circuito corresponde a um amplificador na configuração "
            "emissor comum."),
    },
    {
        "arquivo": "378_ABIN_CB3_01.PDF", "cargo": AGENTE, "numero": 45,
        "gabarito": "certo", "texto": TEXTO_CB3_FIGURAS,
        "enunciado": (
            "Considere que o significado da figura II seja “data: com dia "
            "e mês, nessa ordem”. Nesse caso, há a possibilidade de pelo "
            "menos 7 interpretações para essa figura."),
    },
    {
        "arquivo": "378_ABIN_CB3_01.PDF", "cargo": AGENTE, "numero": 46,
        "gabarito": "errado", "texto": TEXTO_CB3_FIGURAS,
        "enunciado": (
            "Considere que o significado da figura III seja “data: com "
            "dia, mês e ano entre 2000 e 2100, nessa ordem”. Nesse caso, "
            "há a possibilidade de pelo menos 2 interpretações para essa "
            "figura."),
    },
    {
        "arquivo": "378_ABIN_CB3_01.PDF", "cargo": AGENTE, "numero": 47,
        "gabarito": "errado", "texto": TEXTO_CB3_FIGURAS,
        "enunciado": (
            "Se o significado da figura I for “ano do século passado”, "
            "existem pelo menos dois anos que podem estar representados "
            "nessa figura."),
    },
]

CONTAGENS_CANONICAS = {
    "378_ABIN_001_01.PDF": 82,
    "378_ABIN_002_01.PDF": 89,
    "378_ABIN_003_01.PDF": 89,
    "378_ABIN_004_01.PDF": 89,
    "378_ABIN_005_01.PDF": 82,
    "378_ABIN_006_01.PDF": 87,
    "378_ABIN_007_01.PDF": 90,
    "378_ABIN_008_01.PDF": 86,
    "378_ABIN_009_01.PDF": 85,
    "378_ABIN_010_01.PDF": 89,
    "378_ABIN_011_01.PDF": 90,
    "378_ABIN_012_01.PDF": 88,
    "378_ABIN_013_01.PDF": 90,
    "378_ABIN_014_01.PDF": 87,
    "378_ABIN_015_01.PDF": 70,
    "378_ABIN_CB1_01.PDF": 232,
    "378_ABIN_CB2_01.PDF": 580,
    "378_ABIN_CB3_01.PDF": 50,
}


def numero(q: dict) -> int:
    return int(re.search(r"-(\d+)$", q["id"]).group(1))


def fonte_oficial(cargo: str, n: int) -> str:
    if cargo == OFICIAL:
        return CB1
    if cargo == TECNICO:
        return CB2
    if cargo == AGENTE:
        return CB3 if n <= 50 else AGENTE_ESP
    if m := re.fullmatch(r"Oficial de Inteligência - Área (\d+)", cargo):
        area = int(m.group(1))
        if not 1 <= area <= 4 or not 61 <= n <= 150:
            raise ValueError(f"fora da faixa esperada: {cargo} item {n}")
        return f"{CDN}/378_ABIN_{area:03d}_01.PDF"
    if m := re.fullmatch(r"Oficial Técnico de Inteligência - Área (\d+)", cargo):
        area = int(m.group(1))
        if not 1 <= area <= 10 or not 61 <= n <= 150:
            raise ValueError(f"fora da faixa esperada: {cargo} item {n}")
        return f"{CDN}/378_ABIN_{area + 4:03d}_01.PDF"
    raise ValueError(f"cargo não mapeado: {cargo}")


def slug_prefixo(records: list[dict], cargo: str) -> str:
    ids = [r["id"].rsplit("-", 1)[0] for r in records if r["cargo"] == cargo]
    if len(set(ids)) != 1:
        raise ValueError(f"prefixo de id ambíguo para {cargo}")
    return ids[0]


def registro_faltante(records: list[dict], spec: dict) -> dict:
    base = next(r for r in records if r["cargo"] == spec["cargo"])
    n = spec["numero"]
    return dict(
        base,
        id=f"{slug_prefixo(records, spec['cargo'])}-{n:03d}",
        fonte=f"{CDN}/{spec['arquivo']}",
        enunciado=spec["enunciado"],
        gabarito=spec["gabarito"],
        texto=spec["texto"],
    )


ORDEM_CARGOS = {
    cargo: i for i, cargo in enumerate(
        [f"Oficial de Inteligência - Área {i}" for i in range(1, 5)]
        + [f"Oficial Técnico de Inteligência - Área {i}" for i in range(1, 11)]
        + [AGENTE])
}


def validar_saida(out: list[dict]) -> None:
    """Falha se o resultado não tiver exatamente a forma canônica esperada."""
    if len(out) != 2155:
        raise ValueError(f"saída inesperada: {len(out)} registros")
    ids = [q["id"] for q in out]
    duplicados = sorted(x for x, n in Counter(ids).items() if n > 1)
    if duplicados:
        raise ValueError(f"ids duplicados após a expansão: {duplicados[:5]}")
    if any(q["fonte"] == FONTE_DIR for q in out):
        raise ValueError("fonte-dir sobreviveu ao reparo")
    if {q["cargo"] for q in out} != set(ORDEM_CARGOS):
        raise ValueError("o resultado canônico deve ter exatamente os 15 cargos reais")
    if {OFICIAL, TECNICO} & {q["cargo"] for q in out}:
        raise ValueError("pseudocargo sobreviveu ao reparo")
    if any(q["fonte"] == CB2 and numero(q) == 7 for q in out):
        raise ValueError("item 7 anulado da trilha espanhola de CB2 sobreviveu")
    for q in out:
        n = numero(q)
        if q["fonte"] == CB2 and n in CB2_ESPANHOL and n != 7:
            esperado = CB2_ESPANHOL[n]
            if q["gabarito"] != esperado:
                raise ValueError(f"gabarito espanhol CB2 divergente no item {n}")
        if q["fonte"] == CB3 and n in CB3_ESPANHOL:
            esperado = CB3_ESPANHOL[n]
            if q["gabarito"] != esperado:
                raise ValueError(f"gabarito espanhol CB3 divergente no item {n}")
    por_fonte = Counter(q["fonte"].rsplit("/", 1)[-1] for q in out)
    if por_fonte != Counter(CONTAGENS_CANONICAS):
        raise ValueError(f"contagens por fonte divergem: {por_fonte}")


def entrada_canonica(records: list[dict]) -> bool:
    return (
        len(records) == 2155
        and {q["cargo"] for q in records} == set(ORDEM_CARGOS)
        and all(q["fonte"] != FONTE_DIR for q in records)
    )


def reparar(records: list[dict]) -> tuple[list[dict], Counter]:
    if entrada_canonica(records):
        out = sorted(records, key=lambda q: (ORDEM_CARGOS[q["cargo"]], numero(q)))
        validar_saida(out)
        return out, Counter({"registros": len(out), "canonico_existente": 1})
    if len(records) != 1442:
        raise ValueError(f"baseline inesperado: {len(records)} registros")
    if {r["fonte"] for r in records} != {FONTE_DIR}:
        raise ValueError("o shard não está na forma legada de fonte-dir única")

    alvos = {
        OFICIAL: [f"Oficial de Inteligência - Área {i}" for i in range(1, 5)],
        TECNICO: [f"Oficial Técnico de Inteligência - Área {i}" for i in range(1, 11)],
    }
    prefixos = {
        cargo: slug_prefixo(records, cargo)
        for nomes in alvos.values() for cargo in nomes
    }
    stats: Counter = Counter()
    out: list[dict] = []

    for original in records:
        cargo = original["cargo"]
        n = numero(original)
        fonte = fonte_oficial(cargo, n)
        expandir = alvos.get(cargo, [cargo])
        for alvo in expandir:
            q = dict(original, cargo=alvo, fonte=fonte)
            if alvo != cargo:
                q["id"] = f"{prefixos[alvo]}-{n:03d}"
            if cargo == TECNICO and n in CB2_ESPANHOL:
                q["gabarito"] = CB2_ESPANHOL[n] or q["gabarito"]
            if cargo == AGENTE and n in CB3_ESPANHOL:
                q["gabarito"] = CB3_ESPANHOL[n]
            if cargo == TECNICO and n == 7:
                stats["anulado_es_cb2"] += 1
                continue
            out.append(q)
            stats["registros"] += 1
            if alvo != cargo:
                stats["expandidos"] += 1

    esperado: dict[str, list[int]] = {}
    for spec in FALTANTES_CURADOS:
        esperado.setdefault(spec["arquivo"], []).append(spec["numero"])
    if esperado != FALTANTES_NAO_ANULADOS:
        raise ValueError("patch curado diverge da lista de faltantes não anulados")
    for spec in FALTANTES_CURADOS:
        out.append(registro_faltante(records, spec))
        stats["recuperados"] += 1
    out.sort(key=lambda q: (ORDEM_CARGOS[q["cargo"]], numero(q)))

    validar_saida(out)
    return out, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="regrava data/questions/ABIN_17.json")
    ap.add_argument("--input", type=Path, default=SHARD,
                    help="shard de entrada (padrão: data/questions/ABIN_17.json)")
    ap.add_argument("--output", type=Path,
                    help="escreve o shard reparado em outro caminho")
    args = ap.parse_args()

    records = load_shard_records(args.input)
    out, stats = reparar(records)
    por_fonte = Counter(q["fonte"].rsplit("/", 1)[-1] for q in out)
    if stats["canonico_existente"]:
        print(f"entrada já canônica: {len(records)} registros; "
              "nenhuma transformação necessária")
    else:
        print(f"entrada: {len(records)} registros; saída: {len(out)} "
              f"({stats['expandidos']} registros finais nas provas básicas "
              "compartilhadas, "
              f"{stats['anulado_es_cb2']} omitidos do item 7 anulado em espanhol, "
              f"{stats['recuperados']} recuperados do PDF oficial)")
    print(f"fontes: {len(por_fonte)} PDFs oficiais")
    print("recuperados por conferência manual no PDF renderizado: "
          + "; ".join(f"{nome} itens {nums}"
                       for nome, nums in FALTANTES_NAO_ANULADOS.items()))
    for nome, n in sorted(por_fonte.items()):
        print(f"  {nome}: {n}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
            tmp_path = Path(tmp) / f"{EVENTO}.json"
            write_shard(EVENTO, out, Path(tmp))
            tmp_path.replace(args.output)
        print(f"shard reparado -> {args.output}")
    elif args.write:
        path = write_shard(EVENTO, out)
        print(f"shard regravado -> {path}")
    else:
        print("dry-run — use --write para regravar ou --output para gerar cópia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
