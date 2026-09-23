FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd -r guardarr && useradd -r -g guardarr guardarr

COPY pyproject.toml ./
COPY README.md ./
COPY app ./app

RUN pip install --no-cache-dir -e .

RUN mkdir -p /config /data && chown -R guardarr:guardarr /app /config /data

USER guardarr

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "app.main:application", "--host", "0.0.0.0", "--port", "8000"]
