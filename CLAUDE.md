# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**MCP (Model Context Protocol) server** for resume/candidate processing. Two independent
pieces exist today:

- A **Candidate Skill Agent MCP server** (`server/mcp_server.py` + `server/tools/` +
  `server/prompts/`) exposing 4 tools and 1 prompt, runnable over three transports
  (`stdio`, streamable `http`, `sse`).
- A **provider-agnostic chat-model layer** (`chat_model/` + `config/`) that builds a
  LangChain chat model from `.env`. This is wired for the future — the MCP server does not
  call it yet.

This project was bootstrapped from `labs_mcp_server` (a Weather MCP demo) and upgraded to the
current **`mcp` SDK v2** (`MCPServer`, not the retired `FastMCP` name). The tools/prompts are
ported from `candidate-match-agent`'s in-process Claude-Agent-SDK tools, adapted to the
standalone `mcp` SDK's idioms (see "Porting notes" below).

`main.py` is the CLI entrypoint: it parses `--protocol/--host/--port` and starts the server.
Requires **Python >= 3.14** and **[uv](https://github.com/astral-sh/uv)** for dependency
management (the source of truth — `uv.lock` is committed).

> **Not wired up yet:** this server is not registered with `candidate-match-agent`. That
> integration is a deliberately separate, future step — this repo is meant to be created,
> installed and smoke-tested standalone first.

## Commands

```sh
uv sync                                                               # Install deps + create .venv
uv run pytest                                                         # Run all tests
uv run pytest tests/config/test_settings.py                           # Run one test file
uv run pytest tests/path::test_name                                   # Run a single test
uv run pytest --cov=candidate_skill_agent --cov-report=term-missing   # Run tests with coverage (100% required)
uv run ruff check                                                     # Lint
uv run ruff format                                                    # Format
```

Running the MCP server (defaults: `stdio`, host `127.0.0.1`, port `8000`):

```sh
uv run python -m candidate_skill_agent.main                                 # stdio (default)
uv run python -m candidate_skill_agent.main --protocol http --port 8000     # streamable HTTP -> /mcp
uv run python -m candidate_skill_agent.main --protocol sse  --port 8000     # SSE (legacy)    -> /sse
```

## Architecture

### MCP server (`server/` + `main.py`)

`server/mcp_server.py` owns the `MCPServer` instance (`mcp`) and **how to start itself** via
`run_server(protocol, host, port)`, which maps the CLI-friendly protocol names to `mcp` v2
transports and calls `mcp.run(transport=..., host=..., port=...)` (stdio takes neither
`host` nor `port`). `main.py` stays a thin CLI layer: it only parses args and delegates to
`run_server`.

At the bottom of `mcp_server.py` there are two **absolute** imports —
`from candidate_skill_agent.server import tools` / `prompts` — purely for their
`@mcp.tool()` / `@mcp.prompt()` registration side effects. They're absolute (not relative)
so this file keeps working if something points `mcp dev` directly at its file path instead
of importing the package.

**Tools** (`server/tools/`), one module per tool:

| Tool | File | Notes |
| --- | --- | --- |
| `extract_technical_skills` | `technical_skill_extraction.py` | **Mocked** — fixed payload. |
| `extract_soft_skills` | `soft_skill_extraction.py` | **Mocked** — fixed payload. |
| `extract_certifications` | `certification_skill_extraction.py` | **Mocked** — fixed payload. |
| `extract_languages` | `language_skill_extraction.py` | **Mocked** — fixed payload. |

`server/tools/__init__.py` imports each module conditionally based on
`SkillAgentSettings.active_tools` (see "Tool selection" below) — only an imported module's
`@mcp.tool()` actually registers.

**Prompts** (`server/prompts/`), exposed via `@mcp.prompt()`:

- `coordinator_orchestration` — system prompt for a deterministic coordinator that fans out
  all extraction tools in parallel.

**Adding a tool:** decorate a function with `@mcp.tool()` in a new module under
`server/tools/`, importing `mcp` from `..mcp_server`, then add it to the conditional-import
list in `server/tools/__init__.py` (guarded by its `ToolName` member) so the decorator runs.
The docstring and type hints become the tool's schema, so write them precisely. **Adding a
prompt** follows the same pattern under `server/prompts/` with `@mcp.prompt()`.

### Tool selection (`settings/`)

`settings/settings.py` defines `SkillAgentSettings.active_tools: frozenset[ToolName] | None`,
read from the `CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS` env var (accepts a comma-separated list of
tool names, e.g. `"extract_technical_skills,extract_certifications"`, or a real JSON array).
Unset (the default) registers every tool, which is what local development against the MCP
Inspector wants. A future Helm chart will pin one or more values per deployed pod to restrict
it to a subset of tools. `get_skill_agent_settings()` is an `lru_cache` singleton, mirroring
`config/settings.py`'s `get_settings()`.

### Porting notes (vs. candidate-match-agent's claude-agent-sdk tools)

- One single `MCPServer("CandidateSkillAgent")` instance exposes all 4 tools — not 4 separate
  in-process servers like candidate-match-agent uses for the Claude Agent SDK. Tool names are
  therefore plain (`extract_technical_skills`, ...), with no `mcp__<server>__` prefix (that
  prefix is a claude-agent-sdk/in-process-server artifact).
- Tools **raise** on error (e.g. `RuntimeError` for a simulated mock failure) instead of
  returning the claude-agent-sdk `{"content": [...], "is_error": True}` dict. `mcp` v2 turns
  an uncaught exception into a tool error automatically.
- `coordinator_orchestration`'s tool-name references were adapted from the
  `mcp__<server>__extract_technical_skills`-style composite names to the plain names above.

### Chat-model layer (`config/` + `chat_model/`)

Configuration flows through three provider-agnostic layers so new LLM backends can be
added without touching call sites:

1. **`config/settings.py`** — `Settings` (pydantic-settings) reads `.env` with prefix
   `CHAT_LLM_` (e.g. `CHAT_LLM_API_KEY`, `CHAT_LLM_MODEL`, `CHAT_LLM_CONFIG_ID`).
   `get_settings()` is an `lru_cache` singleton. `Settings.get_chat_model_config()`
   converts env vars into a generic `ChatConfig`.
2. **`config/type.py`** — `ChatConfig` is a frozen dataclass with the fields every
   OpenAI-compatible provider needs (provider, model, api_key, base_url, temperature).
   Provider-specific options go in the `extra` mapping (e.g. Portkey's `config_id`) so the
   schema stays generic. `LLMProvider` is a `StrEnum` of supported backends.
3. **`chat_model/`** — Strategy + factory pattern:
   - `chat.py` — `Chat` ABC; a concrete provider only implements `build_model()`.
   - `portkey.py` — `PortkeyChat`, the only implementation, wraps
     `langchain_openai.ChatOpenAI` pointed at the Portkey gateway (OpenAI-compatible API),
     injecting the `x-portkey-config` header when `config_id` is set.
   - `chat_factory.py` — `_PROVIDERS` maps `LLMProvider` → `Chat` subclass.
     `build_chat_model(config)` dispatches (raising `ValueError` for unregistered
     providers); `get_chat_model()` is the cached top-level accessor that wires
     settings → config → model.

**Adding a new provider:** implement a `Chat` subclass in `chat_model/`, register it in
`_PROVIDERS`, add the enum value in `config/type.py` (if missing), and export it from
`chat_model/__init__.py`. Only `LLMProvider.PORTKEY` is wired today; the other enum values
(`OLLAMA`, `OPENAI`, `ANTHROPIC`, `GEMINI`) have no implementation yet.

The default model is a Claude model served via a Portkey enterprise gateway
(`@aws-bedrock-use2/us.anthropic.claude-sonnet-4-6`), configurable via `.env`.

## Dependencies

- **`mcp[cli]>=2.3.0`** — the standalone MCP Python SDK (v2 line; v1.x is now
  security-fixes-only maintenance). `MCPServer` replaces the retired `FastMCP` name.
- **`labs-agent-lib>=0.4.2`** — shared logging (`get_logger`), reused from
  `candidate-match-agent`'s ecosystem. **Not yet on the real PyPI** — it's resolved from
  TestPyPI via the explicit `[tool.uv.index]` / `[tool.uv.sources]` entries in
  `pyproject.toml`, so plain `uv sync` just works for development. Anyone installing this
  package from the real PyPI with `uvx`/`pip` later will additionally need
  `--extra-index-url https://test.pypi.org/simple/` until `labs-agent-lib` graduates off
  TestPyPI (see `MCP.md`).

## Configuration

Copy `.env.sample` → `.env`. Required: `CHAT_LLM_API_KEY`. Everything else has defaults in
`Settings` (provider `portkey`, the Claude model above, the Portkey gateway URL,
temperature `0.7`). `.env` is git-ignored and read-blocked by project policy — never print
its contents.

## Tests

Tests live under `tests/`, mirroring the package layout (`tests/config/`,
`tests/chat_model/`, `tests/server/`). `tests/server/` covers the tools, prompts and MCP
server wiring; `tests/config/` and `tests/chat_model/` cover the config/chat layer only
(unchanged from `labs_mcp_server`). Unit-test conventions and the 100%-coverage requirement
are defined in `.claude/rules/testing.md`.
