FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.lock ./
RUN python -m pip wheel --wheel-dir /wheels -r requirements.lock
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MEDIA_STORAGE_DIR=/data/media \
    REPORT_EXPORT_DIR=/data/reports

RUN groupadd --gid 10001 breachsim \
    && useradd --uid 10001 --gid breachsim --create-home --shell /usr/sbin/nologin breachsim \
    && mkdir -p /app /data/media /data/reports \
    && chown -R breachsim:breachsim /app /data

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=breachsim:breachsim app ./app
COPY --chown=breachsim:breachsim alembic ./alembic
COPY --chown=breachsim:breachsim scripts ./scripts
COPY --chown=breachsim:breachsim alembic.ini pyproject.toml ./

USER breachsim
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
