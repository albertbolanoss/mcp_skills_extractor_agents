# syntax=docker/dockerfile:1

FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached separately from source changes).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.14-slim

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN mkdir -p /app/documentation/prompt_log /app/documentation/agent_transcript \
    && chown -R appuser:appuser /app/documentation

USER appuser

EXPOSE 8000

# The mcp SDK's streamable-HTTP transport only exposes /mcp (JSON-RPC over POST) - there's no
# dedicated health route to curl, so this checks plain TCP connectivity on $PORT instead.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('127.0.0.1', int(os.environ['PORT']))) == 0 else 1)"]

# Split as ENTRYPOINT + CMD (not one combined CMD) so callers - including the Helm chart,
# which only overrides `args` - can replace just the flags without needing to also repeat
# the binary name.
ENTRYPOINT ["mcp-skills-extractor-agents"]

# stdio (the CLI default) doesn't make sense in a long-running container, so default to
# streamable HTTP bound to all interfaces; the Helm chart overrides these via container args.
CMD ["--protocol", "http", "--host", "0.0.0.0", "--port", "8000"]
