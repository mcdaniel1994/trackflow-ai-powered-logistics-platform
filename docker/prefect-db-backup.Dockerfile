FROM postgres:16@sha256:17e67d7b9890c99b055ba1e0d5c5be4ec27c9d3a72bda32db24a5e5d8a85af0c
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv tini \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/backup-venv \
    && /opt/backup-venv/bin/pip install --no-cache-dir boto3==1.43.48
WORKDIR /app
COPY services/central-api/scripts/prefect_db_backup.py /app/prefect_db_backup.py
RUN chown -R backup:backup /app
USER backup
ENTRYPOINT ["tini", "--"]
CMD ["/opt/backup-venv/bin/python", "/app/prefect_db_backup.py"]
