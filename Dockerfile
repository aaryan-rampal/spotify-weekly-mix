FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
COPY config.yaml ./
COPY scripts/run_all.sh ./scripts/

RUN uv sync --no-dev

# Weekly mix dedup state lives here. Mount a named volume at this path so it
# survives `docker run --rm`, e.g. `-v weekly-mix-state:/app/state`.
ENV WEEKLY_MIX_STATE_PATH=/app/state/weekly_mix_runs.json
VOLUME ["/app/state"]

ENTRYPOINT ["./scripts/run_all.sh"]
