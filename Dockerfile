# papiro — imagem única para `api` e `crawler` (ver compose.yaml).
# Os parsers chamam pdftotext/pdftohtml via subprocess -> poppler-utils.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY crawler/requirements.txt crawler/requirements.txt
RUN pip install --no-cache-dir -r crawler/requirements.txt

COPY crawler/ crawler/
COPY api/ api/
# data/ e jobs entram por volume em runtime (ver compose.yaml)

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "crawler", "next"]
