#!/bin/sh
# Role read-only da API (PER-004): SELECT nas tabelas, nada mais.
# Roda só no initdb — volume pgdata NOVO. Em banco existente aplicar os
# GRANTs à mão (ver .agents/docs/docker-postgres.md).
set -eu
: "${POSTGRES_RO_PASSWORD:?defina POSTGRES_RO_PASSWORD (ver .env/)}"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -v ro_pw="$POSTGRES_RO_PASSWORD" \
    -v db="$POSTGRES_DB" -v owner="$POSTGRES_USER" <<'SQL'
CREATE ROLE papiro_ro LOGIN PASSWORD :'ro_pw';
GRANT CONNECT ON DATABASE :"db" TO papiro_ro;
GRANT USAGE ON SCHEMA public TO papiro_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO papiro_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT SELECT ON TABLES TO papiro_ro;
SQL
