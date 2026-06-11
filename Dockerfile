FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
COPY config.yaml ./
COPY scripts/run_all.sh ./scripts/

RUN uv sync --no-dev

ENTRYPOINT ["./scripts/run_all.sh"]
