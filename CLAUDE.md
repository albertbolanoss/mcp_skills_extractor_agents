# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An **MCP server** (`mcp` SDK v2, `MCPServer`) that exposes 4 resume/job-posting skill-extraction
tools and 1 coordinator prompt over `stdio`, streamable `http`, and `sse` transports. Each tool
runs a real **Claude Agent SDK** agent (via `claude-agent-sdk` + `labs-agent-lib`), grounded in
this project's own canonical taxonomies under `server/resources/`.

This repo is the extraction piece of a hub-and-spoke system: `talent-distiller-agent` (sibling
repo) uploads resumes/job postings and runs the coordinator workflow against this server's
tools; `labs-agent-lib` (sibling repo) provides shared Claude Agent SDK config/logging used by
both. This server is currently standalone — not yet registered with `talent-distiller-agent`.

## Commands

```sh
uv sync                                                                    # install deps / create .venv
uv run python -m mcp_skills_extractor_agents.main                         # run server, stdio (default)
uv run python -m mcp_skills_extractor_agents.main --protocol http --port 8000  # streamable HTTP -> /mcp
uv run python -m mcp_skills_extractor_agents.main --protocol sse  --port 8000  # SSE (legacy)    -> /sse

uv run pytest                                                              # run tests
uv run pytest tests/path::test_name                                       # run a single test
uv run pytest --cov=mcp_skills_extractor_agents --cov-report=term-missing  # coverage (100% required, fail_under=100)
uv run ruff check                                                          # lint
uv run ruff format                                                        # format
```

Requires Python >= 3.14. `labs-agent-lib` resolves from TestPyPI (declared in `pyproject.toml`
via `[tool.uv.sources]`) since it isn't on the real PyPI yet. Without a real
Portkey/Anthropic credential in `.env` (copy from `.env.sample`), the server starts fine but
every tool call fails once it reaches the model.

Test conventions (naming, Arrange/Act/Assert structure, fake-patching style, 100% coverage
requirement) are fully specified in `.claude/rules/testing.md` — read it before writing or
modifying any test.

## Architecture

### One `MCPServer` instance, built by side-effecting imports

`server/mcp_server.py` creates the single module-level `mcp = MCPServer("CandidateSkillAgent")`
instance. Tools, prompts, and resources register themselves onto it via the `@mcp.tool()` /
`@mcp.prompt()` decorators as a side effect of being imported — nothing is registered until its
module is imported. `server/mcp_server.py`'s own `run_server()` imports `server/prompts`,
`server/resources`, and `server/tools` (in that order, as absolute imports) right before
`if __name__ == "__main__"`, which is what actually triggers every registration.

### Tool gating via `server/tools/__init__.py`

`SkillAgentSettings.active_tools` (env var `CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS`, comma-separated)
decides which tool submodules `server/tools/__init__.py` imports — and therefore which
`@mcp.tool()` actually registers. `None` (the default) imports all 4. This is how a Helm
deployment pins a subset of tools to a given pod. `EXTRACTION_TOOL_NAMES` (built from whichever
tools actually got registered) feeds into the coordinator prompt so it never references a tool
that isn't live on this server instance.

### The 4 extraction tools are one template, copy-pasted 4 times

`server/tools/{technical_skill,soft_skill,certification_skill,language_skill}_extraction.py`
are structurally identical — when changing the shared behavior (retry loop, observability
wiring, JSON-array extraction, prompt shape), change it in **all four** files, not just one.
Each follows the same shape:

1. An `AgentDefinition` with a pinned model id (`us.anthropic.claude-sonnet-5` — pinned, not
   the `"sonnet"` alias, because the alias can resolve to a model id a given Portkey/Bedrock
   integration hasn't allow-listed yet) and a system prompt that embeds the relevant canonical
   taxonomy/taxonomies as JSON (e.g. technical skills + seniority levels) with instructions to
   normalize whatever the document says to the canonical name.
2. A Pydantic `BaseModel` describing one extracted item, used to validate the agent's JSON.
3. `_build_user_prompt(content, doc_type)` — wraps the document text with a `resume`/`job_posting`
   marker.
4. `_extract_json_array(raw_text)` — tolerates stray prose/markdown fences around the JSON the
   agent returns.
5. `_parse_*(raw_text, doc_type)` — validates against the Pydantic model, then runs each item's
   relevant field(s) through the resource module's `normalize_*()` function. `required` is only
   kept for `doc_type == "job_posting"` (omitted — `exclude_none=True` — for `resume`).
6. `_ask(client, prompt)` — sends a prompt on a live `ClaudeSDKClient`, drains `AssistantMessage`
   text and captures the `session_id` from the terminal `ResultMessage`.
7. The `@mcp.tool()`-decorated function itself: opens one `ClaudeSDKClient` session, loops up to
   `max_retries + 1` attempts, feeding `_CORRECTION_PROMPT` (with the validation error) back to
   the *same* session on failure, logging through `ToolObservability` at every step, and raising
   `RuntimeError` only after every attempt is exhausted.

Every tool also accepts `correlation_id: str = ""`, threaded through unchanged to
`ToolObservability` for cross-service tracing — see below.

### Canonical taxonomies (`server/resources/`)

Each `common_*.py` module (technical skills, soft skills, certifications, languages, language
proficiency levels, seniority levels) is both:
- an `@mcp.resource()`-exposed read endpoint (so an MCP client can introspect the taxonomy), and
- the source of a `normalize_*()` function the extraction tools call to canonicalize the agent's
  output.

Taxonomies are plain dicts mapping a canonical name to its known aliases (e.g.
`COMMON_TECHNICAL_SKILLS` groups by category, each canonical skill -> list of aliases like
`"JavaScript": ["JS", "ECMAScript", "ES6", "ES2015"]`). The full taxonomy JSON gets embedded
directly into each tool's system prompt so the agent normalizes at generation time; the
`normalize_*()` call in `_parse_*` is the second, deterministic safety net against anything the
model still gets wrong.

### Observability: prompt log + agent transcript

`observability/` implements two complementary, file-based JSONL logs shared in spirit with the
sibling `talent_distiller_agent` repo — full design in
`documentation/prompt_log_and_agent_transcript.md`:

- **Prompt log** (`prompt_log.py`) — one flat line per outbound LLM call attempt: "what did we
  ask, and when." Good for searching across many runs.
- **Agent transcript** (`agent_transcript.py`) — one ordered event per step of a single tool
  call (`session_start`, `assistant_text`, `retry`, `session_end`): "what happened in this call,
  attempt by attempt." Good for replaying one call end-to-end.
- **`tool_observability.py`**'s `ToolObservability` is the single recorder each of the 4 tool
  files instantiates per call, wiring both writers so the retry loop's instrumentation
  (`log_attempt_prompt` / `log_attempt_response` / `log_retry` / `log_success` / `log_failure`)
  is identical across all 4 tools without duplicating JSONL-writing logic in each.
- **`_jsonl_writer.py`** is the shared `append_jsonl` helper. Each tool call writes to its own
  file, `{prompt_log_dir|agent_transcript_dir}/{correlation_id}__{tool_name}.jsonl`, because up
  to 4 extraction tools run concurrently for the same `correlation_id` (the coordinator fans
  them all out in one turn) — one file per tool avoids interleaved/corrupted writes.
- `correlation_id` is minted by the *coordinator* (`talent_distiller_agent`), not here; this
  server only threads whatever value it's given through to these writers. It's optional
  (defaults to `""`) so manual MCP Inspector calls keep working without one.
- Both output directories are gitignored (`documentation/{prompt_log,agent_transcript}/*.jsonl`)
  — only `.gitkeep` is committed, because the `content` argument is full resume/job-posting text
  (PII) that these files reproduce verbatim. Controlled by
  `CANDIDATE_SKILL_AGENT_OBSERVABILITY_ENABLED` (default `true`) and the `*_DIR` settings below.

### Settings

`settings/settings.py`'s `SkillAgentSettings` (env prefix `CANDIDATE_SKILL_AGENT_`, cached
singleton via `get_skill_agent_settings()`) holds this server's own config: `active_tools`,
`observability_enabled`, `prompt_log_dir`, `agent_transcript_dir`. Separately, every tool's
actual Claude Agent SDK credentials/provider come from `labs-agent-lib`'s `AgentSettings`
(env prefix `LABS_AGENT_LIB_`, e.g. `LABS_AGENT_LIB_PROVIDER=portkey|anthropic`) — two distinct
settings objects from two different packages, don't conflate their env prefixes.

### Coordinator prompt

`server/prompts/coordinator_orchestration.py` is a single `@mcp.prompt()` returning a static
system prompt for an external coordinator LLM: fan out all tools in `EXTRACTION_TOOL_NAMES` in
parallel in one turn, pass `correlation_id` through unchanged to each, never retry in-session,
emit no prose, and finish with the literal reply `DONE`. This prompt is consumed by
`talent-distiller-agent`, not by anything in this repo.

## Deployment

Two modes, not mutually exclusive: local dev process (commands above) vs. Kubernetes via Helm
(`helm/mcp-skills-extractor-agents/`, see its own README) — the Helm chart is how
`CANDIDATE_SKILL_AGENT_ACTIVE_TOOLS` gets used in practice, pinning a subset of tools per
deployed pod/release rather than running all 4 in one process.
