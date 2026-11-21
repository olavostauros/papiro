from crawler import discover as d


def _por_caderno(m):
    return {p["caderno"]: p for p in m["provas"]}


def test_classify():
    assert d.classify({"nomeArquivo": "057_IBAMA_CB1_01.pdf",
                       "descricaoArquivo": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS"})[0] == "prova"
    assert d.classify({"nomeArquivo": "Gab_Definitivo_057_IBAMA_CB1_01.PDF",
                       "descricaoArquivo": "GABARITO DEFINITIVO – CB"})[0] == "gabarito"
    assert d.classify({"nomeArquivo": "GAB_PRELIMINAR_699_PRF_CF_001_01.PDF",
                       "descricaoArquivo": "GABARITO PRELIMINAR - PROVA OBJETIVA"})[0] == "ignorado"
    assert d.classify({"nomeArquivo": "057_IBAMA_001_DISC.pdf",
                       "descricaoArquivo": "PROVA DISCURSIVA – CARGO 1"})[0] == "ignorado"
    assert d.classify({"nomeArquivo": "X.PDF", "descricaoArquivo":
                       "PROVA OBJETIVA (P1) ... - CARGO 2 - SEM EFEITO"})[0] == "ignorado"
    assert d.classify({"nomeArquivo": "Gab_Definitivo_282_ANVISA_CB1_11_LEDOR.pdf",
                       "descricaoArquivo": "Gabarito Definitivo Ledor"})[0] == "ignorado"


def test_name_key_casa_prova_e_gabarito():
    assert d.name_key("057_IBAMA_CB1_01.pdf", "prova") == \
        d.name_key("Gab_Definitivo_057_IBAMA_CB1_01.PDF", "gabarito")
    assert d.name_key("MATRIZ_954PC_PECB1_00_COM_JUSTIFICATIVA.PDF", "prova") == \
        d.name_key("GAB_DEFINITIVO_MATRIZ_954PC_PECB1_00.PDF", "gabarito")
    assert d.name_key("MATRIZ_039_CAESB_CG3_00_Com Justificativas_OK.pdf", "prova") == "039_CAESB_CG3_00"


def test_ibama25_pareia_por_nome_e_resolve_cargos(evento):
    m = d.mapear_evento(evento("IBAMA_25"), {"IBAMA": ("IBAMA", "ibama")})
    p = _por_caderno(m)
    assert set(p) == {"057_IBAMA_CB1_01", "057_IBAMA_CB2_01", "057_IBAMA_001_01",
                      "057_IBAMA_002_01", "057_IBAMA_003_01"}
    assert all(x["url_gabarito"] and x["pareamento"] == "nome do arquivo" for x in p.values())
    cb2 = p["057_IBAMA_CB2_01"]
    assert [c["numero"] for c in cb2["cargos"]] == [2, 3]          # "CARGOS 2 E 3"
    assert cb2["assunto"] == "Conhecimentos Básicos"
    assert cb2["url_prova"] == "https://cdn.cebraspe.org.br/concursos/IBAMA_25/arquivos/057_IBAMA_CB2_01.pdf"
    assert cb2["orgao"] == "IBAMA" and cb2["id_orgao"] == "ibama" and cb2["ano"] == 2025
    assert p["057_IBAMA_001_01"]["cargos"][0]["nome"] == "Analista Administrativo"
    assert m["nao_mapeados"] == []


def test_pf21_pareia_por_descricao(evento):
    m = d.mapear_evento(evento("PF_21"))
    p = _por_caderno(m)
    agente = p["CARGO_2_AGENTE_DE_POLCIA_FEDERAL"]
    assert agente["url_gabarito"].endswith("GAB_DEFINITIVO_MATRIZ_577_PF_002_00.PDF")
    assert agente["pareamento"] == "descrição"
    assert [c["nome"] for c in agente["cargos"]] == ["Agente de Polícia Federal"]
    assert len(p) == 4


def test_pc_pe_23_ignora_sem_efeito(evento):
    p = _por_caderno(d.mapear_evento(evento("PC_PE_23")))
    assert len(p) == 5
    assert all("SEM EFEITO" not in x["descricao"] for x in p.values())
    assert p["955PC_PE_DELEGADO001_00"]["url_gabarito"].endswith(
        "GAB_DEFINITIVO_MATRIZ_955PC_PE_DELEGADO001_00.PDF")


def test_prf21_curso_formacao_e_sem_gabarito(evento):
    m = d.mapear_evento(evento("PRF_21"))
    p = _por_caderno(m)
    assert p["578_PRF_001_01"]["fase"] == "objetiva"
    assert p["085_PRFCF_001_01"]["fase"] == "curso_formacao"
    sem = {n["arquivo"] for n in m["nao_mapeados"] if n["motivo"] == "prova sem gabarito definitivo"}
    assert "632_PRF_CF_001_01.PDF" in sem


def test_petrobras_todas_as_enfases(evento):
    p = _por_caderno(d.mapear_evento(evento("PETROBRAS_23_NM")))
    assert len(p["822_PETROBRAS_23_CB1_01"]["cargos"]) == 12
    assert p["822_PETROBRAS_23_CB1_01"]["cargo_como"] == "todos os cargos"


def test_cargos_da_prova_intervalos():
    cargos = {n: {"numero": n, "nome": f"C{n}", "id_cargo": f"c{n}"} for n in range(1, 15)}
    cs, _ = d.cargos_da_prova("CONHECIMENTOS GERAIS PARA OS CARGOS DE 4 A 13", "x", cargos)
    assert [c["numero"] for c in cs] == list(range(4, 14))
    cs, _ = d.cargos_da_prova("SOMENTE PARA OS CARGOS 1, 4, 5 e 12", "x", cargos)
    assert [c["numero"] for c in cs] == [1, 4, 5, 12]


def test_limpar_cargo():
    assert d.limpar_cargo("CARGO 1: ANALISTA ADMINISTRATIVO") == "Analista Administrativo"
    assert d.limpar_cargo("Cargo 1: POLICIAL RODOVIÁRIO FEDERAL - Subsídio inicial de R$ 9.899,88.") \
        == "Policial Rodoviário Federal"
    assert d.limpar_cargo("Cargo de Técnico Legislativo – Código: CDAL-015") == "Técnico Legislativo"


def test_descobrir_offline(fake_fetch):
    man = d.descobrir(fake_fetch, conhecidos={}, workers=1, log=lambda *_: None)
    r = man["resumo"]
    assert r["eventos_listados"] == 5 and r["eventos_com_falha"] == 0
    assert r["provas_completas"] >= 5 + 4 + 5 + 13
    assert {p["evento"] for p in man["provas"]} == {"IBAMA_25", "PF_21", "PC_PE_23",
                                                    "PRF_21", "PETROBRAS_23_NM"}
    # filtro por evento
    só = d.descobrir(fake_fetch, eventos_filtro=["ibama_25"], conhecidos={}, workers=1,
                     log=lambda *_: None)
    assert só["resumo"]["eventos_listados"] == 1


def test_slug_cargo_curto_sem_quebrar_palavra():
    assert d.slug_cargo("Técnico Legislativo – Especialidade: Policial Legislativo Federal")[0] \
        == "policial-legislativo"
    assert d.slug_cargo("Especialista em Regulação de Aviação Civil – Área 1")[0] \
        == "especialista-area-1"
    assert d.slug_cargo("Analista Ambiental – Tema 2: Manejo, Conservação e Reabilitação")[0] \
        == "analista-tema-2"
    assert d.slug_cargo("Analista Judiciário – Área: Administrativa – Sem especialidade")[0] \
        == "administrativa"
    assert d.slug_cargo("Agente de Polícia Federal")[0] == "agente-policia-federal"
    longo = "Tecnologista – Área de Atuação: Desenvolvimento Tecnológico Voltado à Infraestrutura"
    s = d.slug_cargo(longo)[0]
    assert len(s) <= d.SLUG_MAX_CHARS
    palavras_ok = set(d._palavras(longo))
    assert all(w in palavras_ok for w in s.split("-"))      # nenhuma palavra cortada


def test_slug_repetido_no_evento_desempata():
    ev = {"eventoCargos": [
        {"idArea": "01", "area": "CARGO 1: ANALISTA – ESPECIALIDADE: CONTABILIDADE"},
        {"idArea": "02", "area": "CARGO 2: TÉCNICO – ESPECIALIDADE: CONTABILIDADE"},
        {"idArea": "03", "area": "CARGO 3: TÉCNICO – ESPECIALIDADE: DIREITO"},
    ]}
    c = d.cargos_do_evento(ev)
    assert c[1]["id_cargo"] == "analista-contabilidade"
    assert c[2]["id_cargo"] == "tecnico-contabilidade"
    assert c[3]["id_cargo"] == "direito"
    assert len({x["id_cargo"] for x in c.values()}) == 3


def test_reaproveita_slug_do_dataset(evento):
    # cargo já ingerido → mesmo id_cargo do dataset (ids existentes não mudam)
    known = {("IBAMA", "Analista Administrativo"): "analista-administrativo",
             ("IBAMA", "Analista Ambiental – Tema 1: Proteção, Licenciamento, Monitoramento "
                       "e Qualidade Ambiental"): "ambiental-tema-1"}
    m = d.mapear_evento(evento("IBAMA_25"), {"IBAMA": ("IBAMA", "ibama")}, known)
    p = {x["caderno"]: x for x in m["provas"]}
    assert p["057_IBAMA_001_01"]["cargos"][0]["id_cargo"] == "analista-administrativo"
    ids = {c["nome"]: c["id_cargo"] for c in p["057_IBAMA_CB2_01"]["cargos"]}
    assert "ambiental-tema-1" in ids.values()               # reaproveitado
    assert "analista-tema-2" in ids.values()                # novo, curto


def test_cargos_conhecidos_le_slug_dos_ids(tmp_path):
    import json
    ds = tmp_path / "q.json"
    ds.write_text(json.dumps([{"id": "cebraspe-2025-ibama-ambiental-tema-2-051",
                               "orgao": "IBAMA", "cargo": "Analista Ambiental – Tema 2"}]),
                  encoding="utf-8")
    assert d.cargos_conhecidos(ds) == {("IBAMA", "Analista Ambiental – Tema 2"): "ambiental-tema-2"}


def test_orgao_por_sigla_do_evento():
    assert d.orgao_por_sigla("PC_MG") == "Polícia Civil de Minas Gerais"
    assert d.orgao_por_sigla("CBM_MA") == "Corpo de Bombeiros Militar do Maranhão"
    assert d.orgao_por_sigla("POLC_AL") == "Polícia Científica de Alagoas"
    assert d.orgao_por_sigla("TRF6") is None
    ev = {"eventoURL": "PM_PA_23_CFP", "eventoNomeCompleto": "Praças da Polícia Militar do Pará"}
    assert d.orgao_de(ev, {})[:2] == ("Polícia Militar do Pará", "pmpa")
    # órgão já conhecido no dataset tem precedência
    assert d.orgao_de({"eventoURL": "PC_DF_26_DELEGADO"}, {"PC_DF": ("Polícia Civil do Distrito Federal", "pcdf")})[0] \
        == "Polícia Civil do Distrito Federal"
