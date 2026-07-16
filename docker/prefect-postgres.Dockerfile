FROM postgres:16@sha256:17e67d7b9890c99b055ba1e0d5c5be4ec27c9d3a72bda32db24a5e5d8a85af0c

COPY --chmod=0444 docker/prefect-postgres-init.sql /docker-entrypoint-initdb.d/10-pg-trgm.sql
COPY --chmod=0555 docker/prefect-postgres-backup-role.sh /docker-entrypoint-initdb.d/20-backup-role.sh
COPY --chmod=0555 docker/prefect-postgres-guard-role.sh /docker-entrypoint-initdb.d/30-guard-role.sh
COPY --chmod=0555 docker/prefect-postgres-bootstrap.sh /usr/local/bin/prefect-postgres-bootstrap
COPY --chmod=0555 docker/prefect-postgres-guard.sh /usr/local/bin/prefect-postgres-guard
