# candidate-skill-agent

An **MCP (Model Context Protocol) server** for resume/candidate processing, built on the
current `mcp` SDK v2 (`MCPServer`). It ships 5 tools and 2 prompts, runnable over three
transports (`stdio`, streamable `http`, `sse`), plus a provider-agnostic **chat-model layer**
(LangChain + Portkey) wired for future use.

Bootstrapped from [`labs_mcp_server`](https://github.com/albertbolanoss/labs_mcp_server) (a
Weather MCP demo). Tools and prompts are ported from `candidate-match-agent`'s in-process
Claude-Agent-SDK tools — see [CLAUDE.md](CLAUDE.md) for the porting notes.

> **Standalone for now.** This server is not yet registered with `candidate-match-agent` —
> that integration is a deliberate, separate next step. This repo is meant to be created,
> installed and smoke-tested on its own first.

Requires **Python >= 3.14** and **[uv](https://github.com/astral-sh/uv)**.

## Tools

| Tool | Description |
| --- | --- |
| `read_document` | Extracts text from a resume/job posting (`.pdf`, `.docx`, `.txt`, `.md`, `.markdown`). Real implementation via `labs-agent-lib`. |
| `extract_technical_skills` | **Mocked.** Returns a fixed technical-skills payload. |
| `extract_soft_skills` | **Mocked.** Returns a fixed soft-skills payload. |
| `extract_certifications` | **Mocked.** Returns a fixed certifications payload. |
| `extract_languages` | **Mocked.** Returns a fixed spoken-languages payload. |

Set `MOCK_FAIL_ONCE_FIELDS="technical_skills,certifications"` to make a mocked extraction
tool raise once on its first call (then succeed), useful for testing retry logic.

## Prompts

| Prompt | Description |
| --- | --- |
| `document_read` | System prompt for an agent that calls `read_document`. |
| `coordinator_orchestration` | System prompt for a coordinator that reads the document, then fans out all extraction tools in parallel. |

## Setup

```sh
uv python install 3.14      # once, if you don't have Python 3.14
uv sync                     # install dependencies and create .venv
cp .env.sample .env         # then set CHAT_LLM_API_KEY (see Configuration)
```

`uv sync` resolves `labs-agent-lib` from TestPyPI automatically (declared in
`pyproject.toml`) — no extra flags needed for local development.

## Configuration


## Run the MCP server

Defaults: `stdio` transport, host `127.0.0.1`, port `8000`.

```sh
uv run python -m candidate_skill_agent.main                              # stdio (default)
uv run python -m candidate_skill_agent.main --protocol http --port 8000  # streamable HTTP -> /mcp
uv run python -m candidate_skill_agent.main --protocol sse  --port 8000  # SSE (legacy)    -> /sse
```

> SSE is kept for parity with the three transports but is considered **legacy** in `mcp` v2
> ("don't build anything new on it") — prefer `stdio` or `http` for new integrations.

## Develop

```sh
uv run pytest                          # run tests
uv run pytest tests/path::test_name    # run a single test
uv run ruff check                      # lint
uv run ruff format                     # format
```

## More

See **[SETUP.md](SETUP.md)** for debugging with the MCP Inspector and registering the
server with Claude Code, **[CLAUDE.md](CLAUDE.md)** for the architecture overview, and
**[MCP.md](MCP.md)** for publishing this project as a package.
