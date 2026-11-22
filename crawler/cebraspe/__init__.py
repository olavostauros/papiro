"""Zero-credit Cebraspe ingestion pipeline (operação papiro).

Local pipeline: download prova/gabarito PDFs from the Cebraspe CDN with
urllib/curl, parse items with pdftohtml -xml coordinates and gabaritos with
pdftotext -layout. No Firecrawl credits involved.

CLI (run from repo root):
    python -m crawler.cebraspe next [--limit N]      rank un-ingested events
    python -m crawler.cebraspe files <EVENTO_URL>    list provas/gabaritos/cargos
    python -m crawler.cebraspe fetch <EVENTO_URL>    download PDFs to workdir
    python -m crawler.cebraspe audit --workdir DIR   parse + audit all files
    python -m crawler.cebraspe plan --workdir DIR    draft job.json from API
    python -m crawler.cebraspe assemble --workdir DIR [--write]
"""
