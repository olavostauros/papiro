"""Cebraspe public API + CDN access. All free, no Firecrawl."""
import json
import re
import urllib.request

LIST_URL = "https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos"
DETAIL_URL = "https://apis.cebraspe.org.br/cebraspe/eventos/{id}"
CDN = "https://cdn.cebraspe.org.br/concursos/{evento}/arquivos/{nome}"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def list_eventos():
    """Flattened list of events across all fases."""
    data = json.loads(_get(LIST_URL))
    return [e for fase in data for e in fase["eventos"]]


def get_evento(ref):
    """Fetch detail by eventoURL slug (numeric id returns 204)."""
    if str(ref).isdigit():
        ref = next(e["eventoURL"] for e in list_eventos()
                   if e["idEvento"] == int(ref))
    return json.loads(_get(DETAIL_URL.format(id=ref)))


def download(evento_url, nome_arquivo, dest):
    nome = urllib.parse.quote(nome_arquivo)
    with open(dest, "wb") as f:
        f.write(_get(CDN.format(evento=evento_url, nome=nome)))
    return dest


def arquivo_kind(arq):
    """Classify an arquivosGabarito entry: 'gabarito' | 'prova' | 'outro'."""
    nome = arq["nomeArquivo"].upper()
    desc = (arq.get("descricaoArquivo") or "").upper()
    if "DISCURSIVA" in desc or "CAPA" in desc:
        return "outro"
    if nome.startswith("GAB") or "GABARITO" in desc:
        return "gabarito"
    if "RESPOSTA" in desc or nome.startswith("RESP"):
        return "gabarito"
    if nome.startswith(("DISC", "EDIT")) or "EDITAL" in desc:
        return "outro"
    return "prova"


# "CARGO 3", "DISCIPLINA 10", "ÁREA 01" etc -> idArea list
_CARGO_RE = re.compile(r"(?:CARGOS?|DISCIPLINAS?|ÁREAS?)\s*(?:DE\s*)?(\d+)", re.I)


def arquivo_cargos(arq):
    """Cargo idAreas referenced by this arquivo's descricao."""
    desc = arq.get("descricaoArquivo") or ""
    return _CARGO_RE.findall(desc)
