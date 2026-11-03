# Unit test conventions

Tests live under `tests/`, mirroring the package layout under `src/candidate_skill_agent/`
(e.g. `src/.../server/mcp_server.py` -> `tests/server/test_mcp_server.py`,
`src/.../settings/settings.py` -> `tests/settings/test_settings.py`).

**Coverage is required to be 100%** (statement coverage, enforced via `fail_under = 100` in
`[tool.coverage.report]` in `pyproject.toml`). Run
`uv run pytest --cov=candidate_skill_agent --cov-report=term-missing` to check it. Any new or
changed source line needs a test that exercises it; don't reach for `# pragma: no cover` to
paper over an untested branch. The only standing exclusion is the
`if __name__ == "__main__":` entrypoint guard, carved out project-wide via `exclude_also` in
`[tool.coverage.report]` since it can't be hit by an import-based test run.

## Rules for writing a test

- **One test module per source module**, named `test_<module>.py`, opening with a one-line
  docstring naming what's under test (e.g. `"""Tests for the Claude-agent-backed
  technical-skills extraction tool."""`).
- **Plain pytest functions, not `unittest.TestCase` classes.** Name each test
  `test_<function_or_behavior>_<scenario>` so the scenario is readable from the test name
  alone (e.g. `test_extract_technical_skills_retries_on_invalid_json`,
  `test_normalize_certification_returns_none_for_unknown_certification`).
- **Structure every test body with `# Arrange` / `# Act` / `# Assert` comments**, even when a
  section is a single line. Lookup-style tests with no setup collapse to `# Act / Assert`.
- **Async tests need no decorator or marker.** `asyncio_mode = "auto"` in
  `[tool.pytest.ini_options]` handles it — just declare `async def test_...(...)`.
- **Fake external dependencies by patching the module under test's bound name**, not the
  original definition: `from ... import x as module` then
  `monkeypatch.setattr(module, "Dependency", fake)`. This is why every extraction-tool test
  module imports its subject `as module` in addition to importing the function directly.
- **Test doubles are small, local, and documented.** A one-line docstring on the fake class
  explains what real object it stands in for and the contract it fakes (e.g. `_FakeClient`:
  "Fakes ClaudeSDKClient: replays queued agent text responses, one per query() call."). A
  `_mock_agent(monkeypatch, responses)` helper wires the fake into the module for a single
  test; both the class and the helper are prefixed `_` as test-local, not part of the public
  surface.
- **Assert whole structures, not fragments.** Prefer `assert result == [{...}]` over checking
  individual keys piecemeal, and use `pytest.raises(RuntimeError)` (or the specific exception)
  for error paths instead of inspecting error strings.
- **Cover both input variants a tool branches on**, even when they don't add statement
  coverage — e.g. both `"resume"` (which omits `required`) and `"job_posting"` (which includes
  it) get their own test, because they document real, divergent behavior.
- **Add a test for every new branch**, including edge-handling paths that are easy to miss,
  like the markdown-code-fence stripping in each tool's `_extract_json_array` helper
  (`test_extract_technical_skills_strips_markdown_code_fences` and its siblings).
