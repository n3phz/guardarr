FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Saltbox-compatible runtime identity (override via -e PUID=... -e PGID=...).
# Defaults preserve the original system-user behavior (uid 100 / gid 101).
ENV PUID=100 \
    PGID=101

WORKDIR /app

RUN groupadd -r guardarr -g "${PGID}" && useradd -r -g guardarr -u "${PUID}" guardarr

COPY pyproject.toml ./
COPY README.md ./
COPY app ./app

RUN pip install --no-cache-dir -e .

RUN mkdir -p /config /data && chown -R guardarr:guardarr /app /config /data

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:application", "--host", "0.0.0.0", "--port", "8000"]
