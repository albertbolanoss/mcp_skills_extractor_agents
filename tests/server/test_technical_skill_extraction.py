"""Tests for the thin MCP tool wrapper delegating to the technical-skills pipeline."""

import pytest

# `extract_technical_skills` imports `run_technical_skills_pipeline` lazily, inside
# its own body (see the comment in technical_skill_extraction.py), so there is no
# module-level binding on the tool module itself to patch. Patch it at its source
# package instead - the lazy `from ... import run_technical_skills_pipeline` resolves
# against this same (patched) module object at call time.
import mcp_skills_extractor_agents.agents.technical_skills as pipeline_package
from mcp_skills_extractor_agents.server.tools.technical_skill_extraction import (
    extract_technical_skills,
)


async def test_extract_technical_skills_delegates_to_the_pipeline(monkeypatch):
    # Arrange
    captured = {}

    async def fake_pipeline(
        *, content, doc_type, max_retries, correlation_id, report_progress
    ):
        captured["content"] = content
        captured["doc_type"] = doc_type
        captured["max_retries"] = max_retries
        captured["correlation_id"] = correlation_id
        return [{"skill": "Python"}]

    monkeypatch.setattr(
        pipeline_package, "run_technical_skills_pipeline", fake_pipeline
    )

    # Act
    result = await extract_technical_skills(
        "Used Python for 5 years", "resume", max_retries=1, correlation_id="corr-1"
    )

    # Assert
    assert result == [{"skill": "Python"}]
    assert captured == {
        "content": "Used Python for 5 years",
        "doc_type": "resume",
        "max_retries": 1,
        "correlation_id": "corr-1",
    }


async def test_extract_technical_skills_uses_default_max_retries_and_correlation_id(
    monkeypatch,
):
    # Arrange
    captured = {}

    async def fake_pipeline(
        *, content, doc_type, max_retries, correlation_id, report_progress
    ):
        captured["max_retries"] = max_retries
        captured["correlation_id"] = correlation_id
        return []

    monkeypatch.setattr(
        pipeline_package, "run_technical_skills_pipeline", fake_pipeline
    )

    # Act
    result = await extract_technical_skills("No skills here", "job_posting")

    # Assert
    assert result == []
    assert captured == {"max_retries": 2, "correlation_id": ""}


async def test_extract_technical_skills_propagates_pipeline_failure(monkeypatch):
    # Arrange
    async def fake_pipeline(
        *, content, doc_type, max_retries, correlation_id, report_progress
    ):
        raise RuntimeError("agent failed to produce valid JSON")

    monkeypatch.setattr(
        pipeline_package, "run_technical_skills_pipeline", fake_pipeline
    )

    # Act / Assert
    with pytest.raises(RuntimeError):
        await extract_technical_skills("whatever", "resume")


async def test_extract_technical_skills_relays_progress_to_the_mcp_context(monkeypatch):
    # Arrange: a `ctx` with a `report_progress` the real MCPServer.Context exposes,
    # confirming the wrapper's progress callback reaches it instead of silently no-oping.
    reported: list[tuple[float, str | None]] = []

    class _FakeContext:
        async def report_progress(self, progress, total=None, message=None):
            reported.append((progress, message))

    captured_report_progress = {}

    async def fake_pipeline(
        *, content, doc_type, max_retries, correlation_id, report_progress
    ):
        captured_report_progress["callback"] = report_progress
        await report_progress("extractor attempt 1/1")
        return []

    monkeypatch.setattr(
        pipeline_package, "run_technical_skills_pipeline", fake_pipeline
    )

    # Act
    await extract_technical_skills("whatever", "resume", ctx=_FakeContext())

    # Assert
    assert reported == [(0, "extractor attempt 1/1")]


async def test_extract_technical_skills_progress_callback_is_a_no_op_without_context(
    monkeypatch,
):
    # Arrange: no `ctx` (e.g. a direct/manual call) must not blow up when the pipeline
    # invokes the progress callback.
    async def fake_pipeline(
        *, content, doc_type, max_retries, correlation_id, report_progress
    ):
        await report_progress("extractor attempt 1/1")
        return []

    monkeypatch.setattr(
        pipeline_package, "run_technical_skills_pipeline", fake_pipeline
    )

    # Act / Assert
    result = await extract_technical_skills("whatever", "resume")
    assert result == []
