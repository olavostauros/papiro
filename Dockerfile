# papiro — imagem única para `api` e `crawler` (ver compose.yaml).
# Os parsers chamam pdftotext/pdftohtml via subprocess -> poppler-utils.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 papiro

WORKDIR /app

COPY crawler/requirements.txt crawler/requirements.lock crawler/
# requirements.txt é o input; requirements.lock (uv pip compile --generate-hashes)
# é o que a imagem instala — regenerar ao mexer nas deps
RUN pip install --no-cache-dir --require-hashes -r crawler/requirements.lock

COPY --chown=papiro:papiro crawler/ crawler/
COPY --chown=papiro:papiro api/ api/
# único subagente embarcado — `auditor` administra a stack na VM
# (descoberto como agente de projeto quando a sessão roda com cwd=/app).
# Agentes novos NÃO entram na imagem a menos que tenham COPY explícito.
COPY --chown=papiro:papiro .agents/agents/auditor.md .agents/agents/auditor.md
# data/ e jobs entram por bind mount em runtime (ver compose.yaml);
# crawler/.cache e work/ são named volumes — o dono tem que ser o usuário
# da imagem para o primeiro mount herdar permissão de escrita
RUN install -d -o papiro -g papiro /app/work /app/crawler/.cache

USER papiro
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "crawler", "next"]
