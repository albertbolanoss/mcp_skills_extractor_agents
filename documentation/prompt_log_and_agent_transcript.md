# Prompt Log & Agent Transcript

This document explains the observability feature added to **both** this repo
(`mcp-skills-extractor-agents`, the MCP server exposing the 4 extraction sub-agents) and
`talent_distiller_agent` (the sibling Coordinator that calls into it). It is one feature
implemented twice, as a complementary pair, so a single file-processing run can be
reconstructed end-to-end across both services.

## 1. Two concepts, not one

| | Prompt Log | Agent Transcript |
|---|---|---|
| **Answers** | "What did we ask the model, and when?" | "What actually happened in this tool call, attempt by attempt?" |
| **Shape** | One flat line per outbound LLM call attempt | One ordered sequence of events per tool call |
| **Good for** | Fast search/filter across many runs | Replaying a single tool call end-to-end, including every self-correction retry |
| **File** | `documentation/prompt_log/{correlation_id}__{tool_name}.jsonl` | `documentation/agent_transcript/{correlation_id}__{tool_name}.jsonl` |

Neither existed before this change. Previously, this server only emitted plain, leveled
`logging` output via `labs_agent_lib.get_logger` ("attempt 2/3 returned invalid output") -
useful for watching a live pod, but not a durable, structured record of what was actually
sent to or returned by the model, and nothing tied a call back to the coordinator run that
triggered it.

## 2. Why this matters

- **Debugging a bad extraction.** When `extract_technical_skills` comes back with the
  wrong seniority level, the transcript shows the exact prompt sent (including the
  canonical taxonomy grounding) and the exact raw text the model replied with for every
  attempt - no need to reproduce the bug live against a real LLM.
- **Audit / compliance.** Resumes and job postings carry candidate PII. Knowing precisely
  what text was sent to a third-party model gateway (Portkey/Anthropic) for a given
  extraction call is a reasonable compliance ask.
- **Watching the self-correction loop.** Each tool retries up to `max_retries` times
  (default 2) on invalid JSON, re-prompting on the *same* `ClaudeSDKClient` session. The
  transcript's `retry` events capture the exact validation error that triggered each
  follow-up turn - this is the one thing plain logging already hinted at
  (`logger.warning("... attempt %d/%d returned invalid output: %s", ...)`) but never
  persisted anywhere durable.
- **Onboarding.** A new engineer can read one `correlation_id`'s files across both repos
  and see the whole hub-and-spoke flow for a single file, turn by turn.

## 3. Correlation across two services

**The constraint:** the real Claude Agent SDK `session_id` for a sub-agent call is only
known *after* its `ClaudeSDKClient` turn finishes (`ResultMessage`), and this server has
no visibility into the coordinator's own session at all - it only sees whatever arguments
arrive in a `tools/call` request.

**The fix:** `talent_distiller_agent` mints a `correlation_id` (`uuid4().hex`) once per
file-processing job and passes it as a new, optional `correlation_id: str = ""` argument
on every extraction tool call (`extract_technical_skills`, `extract_soft_skills`,
`extract_certifications`, `extract_languages` - see `server/tools/`). This server simply
threads that value through to its own prompt-log/transcript writers; it never generates or
validates it. `correlation_id` is optional (defaults to `""`) so manual calls via the MCP
Inspector or `claude mcp add` keep working without it - see `doc/MCP_SETUP.md`.

Because up to 4 extraction calls run **concurrently** for the same `correlation_id` (the
coordinator fans them all out in one turn), each tool gets its **own** file -
`{correlation_id}__{tool_name}.jsonl` - instead of sharing one file per `correlation_id`,
so concurrent writes never interleave or corrupt each other.

```
1 resume  ->  1 correlation_id
              |
              +-- documentation/agent_transcript/{correlation_id}.jsonl                              (sibling repo: 1 Coordinator session)
              +-- documentation/agent_transcript/{correlation_id}__extract_technical_skills.jsonl     (this repo)
              +-- documentation/agent_transcript/{correlation_id}__extract_soft_skills.jsonl          (this repo)
              +-- documentation/agent_transcript/{correlation_id}__extract_certifications.jsonl       (this repo)
              +-- documentation/agent_transcript/{correlation_id}__extract_languages.jsonl            (this repo)
```

Each tool call still records its *own* Claude `session_id` once known (captured by `_ask`
from the attempt's `ResultMessage` and written on `assistant_text` events) - it's just not
the id that ties the two services together, since it doesn't exist until after the call.

## 4. JSONL schema

Both files share an envelope:

```json
{"timestamp": "2026-01-15T10:03:22.104+00:00", "correlation_id": "9f1c...", "service": "mcp_skills_extractor_agents", "agent": "extract_technical_skills", "session_id": null, "event": "..."}
```

**Prompt log** - one `"event": "prompt"` line per outbound LLM call attempt (attempt 1 is
the initial ask, attempt 2+ are self-correction turns):

```json
{"timestamp": "...", "correlation_id": "9f1c...", "service": "mcp_skills_extractor_agents", "agent": "extract_technical_skills", "event": "prompt", "model": "us.anthropic.claude-sonnet-5", "system_prompt_name": "extract_technical_skills", "user_prompt": "Document type: resume\n\nExtract every technical skill...", "attempt": 1}
```

**Agent transcript** - one line per step, `event` is one of:

| `event` | When | Key fields |
|---|---|---|
| `session_start` | Once, on attempt 1 only | `model`, `system_prompt` (logged once, not repeated every attempt), `user_prompt` |
| `assistant_text` | After every `_ask()` call returns | `text` (the raw response), `session_id` |
| `retry` | Every time validation fails and a self-correction turn is queued | `attempt`, `attempts`, `error` |
| `session_end` | Once, on success or once every attempt is exhausted | `is_error`, `result` (on success) or `error` (on failure) |

The two writer classes (`PromptLogWriter`, `AgentTranscriptWriter`) are **centralized in
`labs_agent_lib.observability`** (`labs-agent-lib`, the shared package) - not in this
repo - because `talent_distiller_agent`'s Coordinator needs the exact same JSONL
mechanics and event schema, just keyed one file per plain `{correlation_id}` instead of
per `{correlation_id}__{tool_name}` (see that repo's own
`documentation/prompt_log_and_agent_transcript.md` for why). Each project still supplies
its *own* settings object (`SkillAgentSettings.observability_enabled`/`prompt_log_dir`/
`agent_transcript_dir`) and a `service` name at construction time - nothing about the
`CANDIDATE_SKILL_AGENT_*` env vars moved.

What **does** stay local to this repo is `src/mcp_skills_extractor_agents/observability/tool_observability.py`
(`ToolObservability`) - a small per-call recorder that constructs the shared writers with
`service="mcp_skills_extractor_agents", key_by_agent=True` and exposes the 5 methods each
tool file's retry loop needs (`log_attempt_prompt`, `log_attempt_response`, `log_retry`,
`log_success`, `log_failure`), so the 4 near-identical tool files in `server/tools/` are
instrumented identically without duplicating that wiring 4 times. Each tool's retry loop
(`_ask` + the `try`/`except` around `_parse_*`) already was the shared
validate/self-correct/fail pattern described in
`documentation/design/mcp_skills_extractor_agents_architecture.mmd` in the sibling repo;
this feature adds a durable line next to every step of that loop without changing its
behavior.

## 5. Where files live, and PII handling

Both directories are **gitignored** (`documentation/prompt_log/*.jsonl`,
`documentation/agent_transcript/*.jsonl` in `.gitignore`) - only a `.gitkeep` placeholder
is committed. The `content` argument these tools receive is the full resume/job-posting
text, which these files can reproduce verbatim, so they must never be committed or shared
outside the environment that produced them.

## 6. Configuration

| Setting (`CANDIDATE_SKILL_AGENT_` prefix) | Default | Purpose |
|---|---|---|
| `OBSERVABILITY_ENABLED` | `true` | Master on/off switch for both writers. |
| `PROMPT_LOG_DIR` | `documentation/prompt_log` | Where prompt-log JSONL files are written. |
| `AGENT_TRANSCRIPT_DIR` | `documentation/agent_transcript` | Where transcript JSONL files are written. |

(`talent_distiller_agent` exposes the equivalent three settings under its own
`TALENT_DISTILLER_AGENT_` prefix.)

## 7. Known limitation

This server is designed to run as a horizontally scaled, independently deployed
Kubernetes service (see `helm/mcp-skills-extractor-agents/`) with pod-local, ephemeral
storage. This feature is file-based by design for local/dev-mode observability and to
establish the schema and `correlation_id` contract between the two services. Shipping
these events to a persistent or centralized sink (e.g. a mounted volume, an object store,
or an OpenTelemetry/log-aggregation backend - the `mcp` SDK already ships an unused
`OpenTelemetryMiddleware` that could be wired in later) is future work, not implemented
here.

## 8. Depending on `labs-agent-lib`

`labs-agent-lib>=0.1.0` (the real, production PyPI release - independently versioned
from its TestPyPI history, which already had this same observability module at `0.5.0`)
is required; earlier real-PyPI releases don't exist, since `0.1.0` was its first
production publish. No `[tool.uv.sources]` override is needed - `pyproject.toml`
resolves it from the default index. The `testpypi` index entry is kept only for testing
future prereleases there before cutting a real release.
