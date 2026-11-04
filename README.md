# candidate-skill-agent

An **MCP (Model Context Protocol) server** for resume/job-posting skill extraction, built on
the `mcp` SDK v2 (`MCPServer`). It exposes 4 extraction tools and 1 coordinator prompt over
three transports (`stdio`, streamable `http`, `sse`).

Each tool runs a real **Claude Agent SDK** agent (via `claude-agent-sdk` + `labs-agent-lib`),
grounded in this project's own canonical taxonomies (technical skills, soft skills,
certifications, languages, seniority levels) under `server/resources/`. The agent's JSON
output is validated and, on failure, self-corrected through a few follow-up turns.

This server is the extraction piece of a larger hub-and-spoke system:

| Repository | Role |
| --- | --- |
| [`talent-distiller-agent`](https://github.com/albertbolanoss/talent_distiller_agent) | Uploads resumes/job postings and runs the coordinator workflow. |
| **`candidate-skill-agent`** (this repo) | MCP server exposing the specialized extraction tools used above. |
| [`labs-agent-lib`](https://github.com/albertbolanoss/labs-agent-lib) | Shared Claude Agent SDK config/logging used by both. |

> **Standalone for now.** This server isn't registered with `talent-distiller-agent` yet —
> that integration is a deliberate, separate step. This repo can be installed and
> smoke-tested on its own first.

Requires **Python >= 3.14** and **[uv](https://github.com/astral-sh/uv)**.

## Tools

| Tool | Description |
| --- | --- |
| `extract_technical_skills` | Technical skills, with seniority level and years of experience. |
| `extract_soft_skills` | Soft skills, with seniority level and years of experience. |
| `extract_certifications` | Professional certifications, with issuer and active status. |
| `extract_languages` | Spoken/written languages, with CEFR proficiency level and native status. |

Every tool is backed by a real Claude Agent SDK agent — see "Configuration" below for the
credentials they need to actually run.

Set `CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS=extract_technical_skills,extract_certifications` (or
any subset) to restrict this server to only those tools. Unset (the default) registers all 4.

## Prompts

| Prompt | Description |
| --- | --- |
| `coordinator_orchestration` | System prompt for a coordinator that fans out all extraction tools in parallel. |

## How to run it

- **Development mode** (this machine, Python + `uv`): see below.
- **Deployment mode** (Kubernetes/minikube/Rancher Desktop via Helm): see
  [`helm/mcp-skills-extractor-agents/README.md`](helm/mcp-skills-extractor-agents/README.md).

## Setup

```sh
uv python install 3.14      # once, if you don't have Python 3.14
uv sync                     # install dependencies and create .venv
cp .env.sample .env         # then set the LABS_AGENT_LIB_* credentials below
```

`uv sync` resolves `labs-agent-lib` from TestPyPI automatically (declared in
`pyproject.toml`) — no extra flags needed for local development.

## Configuration

Every tool call goes through a real Claude Agent SDK agent, configured by `labs-agent-lib`'s
`AgentSettings` from `LABS_AGENT_LIB_*` env vars (see `.env.sample`):

| Variable | Description |
| --- | --- |
| `LABS_AGENT_LIB_PROVIDER` | `portkey` (default) or `anthropic`. |
| `LABS_AGENT_LIB_LOG_LEVEL` | Logger verbosity (default `INFO`). |
| `LABS_AGENT_LIB_DISABLE_PROMPT_CACHING` | Disables Claude prompt caching when `true`. |
| `LABS_AGENT_LIB_PORTKEY_BASE_URL` / `LABS_AGENT_LIB_PORTKEY_API_KEY` | Portkey gateway URL and API key — required when `PROVIDER=portkey`. |
| `LABS_AGENT_LIB_PORTKEY_VIRTUAL` | Portkey provider/credential alias (e.g. `aws-bedrock-use2`) — optional. |
| `LABS_AGENT_LIB_ANTHROPIC_BASE_URL` / `LABS_AGENT_LIB_ANTHROPIC_API_KEY` | Anthropic API URL and key — required when `PROVIDER=anthropic`. |

Plus this server's own tool-selection setting:

| Variable | Description |
| --- | --- |
| `CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS` | Comma-separated tool names to restrict this server to. Unset registers all 4 — see "Tools" above. |

Without a real Portkey/Anthropic credential, the server starts fine, but every tool call
fails once it reaches the model.

## Run the MCP server

Defaults: `stdio` transport, host `127.0.0.1`, port `8000`.

```sh
uv run python -m mcp_skills_extractor_agents.main                              # stdio (default)
uv run python -m mcp_skills_extractor_agents.main --protocol http --port 8000  # streamable HTTP -> /mcp
uv run python -m mcp_skills_extractor_agents.main --protocol sse  --port 8000  # SSE (legacy)    -> /sse
```

> SSE is kept for parity with the three transports but is considered **legacy** in `mcp` v2
> ("don't build anything new on it") — prefer `stdio` or `http` for new integrations.

## Develop

```sh
uv run pytest                                                         # run tests
uv run pytest tests/path::test_name                                   # run a single test
uv run pytest --cov=mcp_skills_extractor_agents --cov-report=term-missing   # coverage (100% required)
uv run ruff check                                                     # lint
uv run ruff format                                                    # format
```

## Try it with the MCP Inspector

```sh
npx @modelcontextprotocol/inspector
```

In the Inspector UI: **Transport Type** `STDIO` (it spawns the server itself), or
`Streamable HTTP` with **URL** `http://127.0.0.1:8000/mcp` if you started the server with
`--protocol http`. Click **List Tools** to see every tool registered (or the subset from
`CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS`).

## More

See **[SETUP.md](SETUP.md)** for the full MCP Inspector walkthrough (all three transports)
and registering the server with Claude Code/Desktop, **[CLAUDE.md](CLAUDE.md)** for the
architecture overview, **[MCP.md](MCP.md)** for publishing this project as a package, and
**[helm/mcp-skills-extractor-agents/README.md](helm/mcp-skills-extractor-agents/README.md)**
for deploying this server to Kubernetes.
