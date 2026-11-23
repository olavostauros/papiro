import pytest

from crawler.bancas.cebraspe import api as d


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
    # cargos_ids é chaveado por (norm(orgao), norm(cargo)) — ver cargos_conhecidos
    known = {(d.norm("IBAMA"), d.norm("Analista Administrativo")): "analista-administrativo",
             (d.norm("IBAMA"), d.norm("Analista Ambiental – Tema 1: Proteção, Licenciamento, "
                                      "Monitoramento e Qualidade Ambiental")): "ambiental-tema-1"}
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
    # chaves normalizadas (norm): casa com qualquer casing/acento do manifesto
    assert d.cargos_conhecidos(ds) == \
        {("IBAMA", "ANALISTA AMBIENTAL TEMA 2"): "ambiental-tema-2"}


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


def test_limpar_cargo_quase_todo_maiusculo():
    assert d.limpar_cargo("CARGO 3: SOLDADO DO QUADRO DE PRAÇAS MÚSICOS (QPMus) – ESPECIALIDADE: CLARINETE") \
        .startswith("Soldado do Quadro de Praças Músicos")


# ---------------------------------------------------------------------------
# Validadores e guards de redirect (PER-010/011)
# ---------------------------------------------------------------------------

def test_campo_seguro():
    for v in ("TRF6_24", "PF_18-ADM", "IBAMA_25", "CD_25_NS", "x", "A1"):
        assert d.campo_seguro(v) == v
    for v in ("..", "../x", "a/b", "a\\b", "", ".", "-x", ".x", "_", "x..y",
              "x\x00y", "evento x", "evéntó", "TRF6_24\n"):
        with pytest.raises(ValueError):
            d.campo_seguro(v)


def test_arquivo_seguro():
    for v in ("prova (1).pdf", "057_IBAMA_CB1_01.pdf",
              "MATRIZ_039_CAESB_CG3_00_Com Justificativas_OK.pdf"):
        assert d.arquivo_seguro(v) == v
    for v in ("../x.pdf", "a/b.pdf", "a\\b.pdf", "x..pdf", "", "..", "a/../b"):
        with pytest.raises(ValueError):
            d.arquivo_seguro(v)


class _JsonResp:
    def __init__(self, location=None, data=None):
        self.url = None  # o client falso preenche com a URL requisitada
        self.is_redirect = self.has_redirect_location = location is not None
        self.headers = {"location": location} if location else {}
        self._data = data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _fetch_client(monkeypatch, *resps):
    """Substitui httpx.Client por um fake que serve `resps` em sequência."""
    import httpx
    state = {"resps": list(resps), "urls": []}

    class Fake:
        def get(self, url, **kw):
            state["urls"].append(url)
            r = state["resps"].pop(0)
            r.url = httpx.URL(url)
            return r

    monkeypatch.setattr(httpx, "Client", lambda **kw: Fake())
    return state


def test_fetch_segue_redirect_mesmo_host(tmp_path, monkeypatch):
    alvo = f"{d.API}/tipo/concursos-v2"
    state = _fetch_client(monkeypatch, _JsonResp(location=alvo),
                          _JsonResp(data=[{"x": 1}]))
    fetch = d.make_fetch(cache_dir=tmp_path)
    assert fetch(d.LIST_URL) == [{"x": 1}]
    assert state["urls"] == [d.LIST_URL, alvo]


def test_fetch_recusa_redirect_cross_host_e_downgrade(tmp_path, monkeypatch):
    for loc in ("https://evil.example/x",
                "http://apis.cebraspe.org.br/cebraspe/eventos/x"):
        _fetch_client(monkeypatch, _JsonResp(location=loc))
        with pytest.raises(ValueError, match="redirect"):
            d.make_fetch(cache_dir=tmp_path)(d.LIST_URL)


def test_mesmo_host_redirect_urllib():
    import urllib.request
    h = d._MesmoHostRedirect()
    req = urllib.request.Request(f"{d.CDN}/X_24/arquivos/a.pdf")
    for dest in ("https://evil.example/a.pdf",
                 "http://cdn.cebraspe.org.br/x.pdf",
                 "https://cdn.cebraspe.org.br:444/x.pdf"):
        with pytest.raises(ValueError, match="redirect"):
            h.redirect_request(req, None, 302, "Found", {}, dest)
    novo = h.redirect_request(req, None, 302, "Found", {},
                              f"{d.CDN}/X_24/arquivos/b.pdf")
    assert novo.full_url.endswith("/b.pdf")
