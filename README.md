# About this project

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
| **`mcp-skills-extractor-agents`** (this repo) | MCP server exposing the specialized extraction tools used above. |
| [`labs-agent-lib`](https://github.com/albertbolanoss/labs-agent-lib) | Shared Claude Agent SDK config/logging used by both. |

> **Standalone for now.** This server isn't registered with `talent-distiller-agent` yet —
> that integration is a deliberate, separate step. This repo can be installed and
> smoke-tested on its own first.

Requires **Python >= 3.14** and either [uv](https://github.com/astral-sh/uv) (recommended) or
a plain virtual environment with `pip`.

## Tools

| Tool | Description |
| --- | --- |
| `extract_technical_skills` | Technical skills, with seniority level and years of experience. |
| `extract_soft_skills` | Soft skills, with seniority level and years of experience. |
| `extract_certifications` | Professional certifications, with issuer and active status. |
| `extract_languages` | Spoken/written languages, with CEFR proficiency level and native status. |

Every tool is backed by a real Claude Agent SDK agent — see "Configuring the .env file" below
for the credentials they need to actually run.

Set `MCP_SKILLS_EXTRACTOR_AGENTS_ACTIVE_TOOLS=extract_technical_skills,extract_certifications` (or
any subset) to restrict this server to only those tools. Unset (the default) registers all 4.

Every tool also accepts an optional `correlation_id` argument, propagated by the coordinator
so this call's prompt-log/transcript entries can be joined with the coordinator's own run —
see [`documentation/prompt_log_and_agent_transcript.md`](./documentation/prompt_log_and_agent_transcript.md).

## Prompts

| Prompt | Description |
| --- | --- |
| `coordinator_orchestration` | System prompt for a coordinator that fans out all extraction tools in parallel. |

## How to Run It

There are two ways to run it:

1. **Development mode** (below): run this server directly on your machine with `uv` or a
   plain Python virtual environment.
2. **Deployment mode**: deploy it to a Kubernetes cluster (minikube, Rancher Desktop, or a
   managed/shared cluster) via Helm — see
   [`helm/mcp-skills-extractor-agents/README.md`](helm/mcp-skills-extractor-agents/README.md).

## Development Mode

Development mode runs the MCP server as a plain process on your machine — no containers or
cluster required.

### Prerequisites

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or
   [Python 3.14 or higher](https://www.python.org/downloads/).
2. A Portkey or Anthropic credential for the Claude Agent SDK (ask your AI Academy facilitator
   for a Portkey key, or use an Anthropic API key directly).

### 1. Install Project Dependencies

**Option A: Using uv**

```sh
uv python install 3.14      # once, if you don't have Python 3.14
uv sync                     # install dependencies and create .venv
```

`uv sync` resolves `labs-agent-lib` from TestPyPI automatically (declared in
`pyproject.toml`) — no extra flags needed for local development.

**Option B: Using Python 3.14 and `requirements.txt`**

```sh
# Create and activate a virtual environment in the project root folder
python -m venv .venv
.venv\Scripts\activate

# Install the project dependencies (labs-agent-lib resolves from TestPyPI via the
# --extra-index-url already declared at the top of requirements.txt)
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional: only needed to run tests/lint

# Install the project itself (registers the mcp-skills-extractor-agents entrypoint)
pip install .
```

### 2. Configuring the .env file

Copy the example file and fill in your values:

```sh
cp .env.sample .env
```

Every tool call goes through a real Claude Agent SDK agent, configured by `labs-agent-lib`'s
`AgentSettings` from `LABS_AGENT_LIB_*` env vars:

| Variable | Description |
| --- | --- |
| `LABS_AGENT_LIB_PROVIDER` | `portkey` (default) or `anthropic`. |
| `LABS_AGENT_LIB_LOG_LEVEL` | Logger verbosity (default `INFO`). |
| `LABS_AGENT_LIB_DISABLE_PROMPT_CACHING` | Disables Claude prompt caching when `true`. |
| `LABS_AGENT_LIB_PORTKEY_BASE_URL` / `LABS_AGENT_LIB_PORTKEY_API_KEY` | Portkey gateway URL and API key — required when `PROVIDER=portkey`. |
| `LABS_AGENT_LIB_PORTKEY_VIRTUAL` | Portkey provider/credential alias (e.g. `aws-bedrock-use2`) — optional. |
| `LABS_AGENT_LIB_ANTHROPIC_BASE_URL` / `LABS_AGENT_LIB_ANTHROPIC_API_KEY` | Anthropic API URL and key — required when `PROVIDER=anthropic`. |

Plus this server's own settings:

| Variable | Description |
| --- | --- |
| `MCP_SKILLS_EXTRACTOR_AGENTS_ACTIVE_TOOLS` | Comma-separated tool names to restrict this server to. Unset registers all 4 — see "Tools" above. |
| `MCP_SKILLS_EXTRACTOR_AGENTS_OBSERVABILITY_ENABLED` | Master on/off switch for the prompt log and agent transcript (see [`documentation/prompt_log_and_agent_transcript.md`](./documentation/prompt_log_and_agent_transcript.md)). Defaults to `true`. |
| `MCP_SKILLS_EXTRACTOR_AGENTS_PROMPT_LOG_DIR` | Directory where prompt-log JSONL files are written. Defaults to `documentation/prompt_log`. |
| `MCP_SKILLS_EXTRACTOR_AGENTS_AGENT_TRANSCRIPT_DIR` | Directory where agent-transcript JSONL files are written. Defaults to `documentation/agent_transcript`. |

`.env` is gitignored — never commit it. Without a real Portkey/Anthropic credential, the
server starts fine, but every tool call fails once it reaches the model.

### 3. Run the MCP server

Defaults: `stdio` transport, host `127.0.0.1`, port `8000`.

**Option A: Using uv**

```sh
uv run python -m mcp_skills_extractor_agents.main                              # stdio (default)
uv run python -m mcp_skills_extractor_agents.main --protocol http --port 8000  # streamable HTTP -> /mcp
uv run python -m mcp_skills_extractor_agents.main --protocol sse  --port 8000  # SSE (legacy)    -> /sse
```

**Option B: Using Python and the virtual environment**

```sh
.venv\Scripts\activate

python -m mcp_skills_extractor_agents.main --protocol http --port 8000
# or, once `pip install .` has registered the entrypoint:
mcp-skills-extractor-agents --protocol http --port 8000
```

> SSE is kept for parity with the three transports but is considered **legacy** in `mcp` v2
> ("don't build anything new on it") — prefer `stdio` or `http` for new integrations.

## Deployment Mode

To deploy this server to a Kubernetes cluster (minikube, Rancher Desktop, or a managed/shared
cluster) via Helm instead of running it as a local process, follow
[`helm/mcp-skills-extractor-agents/README.md`](helm/mcp-skills-extractor-agents/README.md). It
covers building the Docker image, installing/upgrading the chart (including running a subset
of tools per release), and reaching the resulting `Service` from inside or outside the
cluster.

## Develop

**Option A: Using uv**

```sh
uv run pytest                                                              # run tests
uv run pytest tests/path::test_name                                       # run a single test
uv run pytest --cov=mcp_skills_extractor_agents --cov-report=term-missing  # coverage (100% required)
uv run ruff check                                                          # lint
uv run ruff format                                                        # format
```

**Option B: Using Python**

```sh
.venv\Scripts\activate

pytest                                                              # run tests
pytest tests/path::test_name                                        # run a single test
pytest --cov=mcp_skills_extractor_agents --cov-report=term-missing  # coverage (100% required)
ruff check                                                          # lint
ruff format                                                         # format
```

## Try it with the MCP Inspector

```sh
npx @modelcontextprotocol/inspector
```

In the Inspector UI: **Transport Type** `STDIO` (it spawns the server itself), or
`Streamable HTTP` with **URL** `http://127.0.0.1:8000/mcp` if you started the server with
`--protocol http`. Click **List Tools** to see every tool registered (or the subset from
`MCP_SKILLS_EXTRACTOR_AGENTS_ACTIVE_TOOLS`).

## More

See **[SETUP.md](SETUP.md)** for the full MCP Inspector walkthrough (all three transports)
and registering the server with Claude Code/Desktop, **[CLAUDE.md](CLAUDE.md)** for the
architecture overview, **[MCP.md](MCP.md)** for publishing this project as a package,
**[documentation/prompt_log_and_agent_transcript.md](documentation/prompt_log_and_agent_transcript.md)**
for the prompt log / agent transcript observability feature shared with
`talent-distiller-agent`, and
**[helm/mcp-skills-extractor-agents/README.md](helm/mcp-skills-extractor-agents/README.md)**
for deploying this server to Kubernetes.
