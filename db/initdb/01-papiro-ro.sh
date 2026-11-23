#!/bin/sh
# Role read-only da API (PER-004): SELECT nas tabelas, nada mais.
# Roda só no initdb — volume pgdata NOVO. Em banco existente aplicar os
# GRANTs à mão (ver .agents/docs/docker-postgres.md).
set -eu
: "${POSTGRES_RO_PASSWORD:?defina POSTGRES_RO_PASSWORD (ver .env/)}"
# A senha vai por arquivo, não por argv do psql (PER-012): o backend lê com
# pg_read_file e format() faz o quoting (%L) — sem segredo em `ps`.
pwfile=$(mktemp)
trap 'rm -f "$pwfile"' EXIT
chmod 600 "$pwfile"
printf %s "$POSTGRES_RO_PASSWORD" > "$pwfile"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -v pwfile="$pwfile" -v db="$POSTGRES_DB" -v owner="$POSTGRES_USER" <<'SQL'
SELECT format('CREATE ROLE papiro_ro LOGIN PASSWORD %L',
              pg_read_file(:'pwfile')) \gexec
GRANT CONNECT ON DATABASE :"db" TO papiro_ro;
GRANT USAGE ON SCHEMA public TO papiro_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO papiro_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT SELECT ON TABLES TO papiro_ro;
SQL
