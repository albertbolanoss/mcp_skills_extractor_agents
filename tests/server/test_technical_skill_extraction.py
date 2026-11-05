"""Tests for the thin extract_technical_skills MCP tool wrapper."""

import mcp_skills_extractor_agents.agents.technical_skills as pipeline_module
from mcp_skills_extractor_agents.server.tools.technical_skill_extraction import (
    extract_technical_skills,
)


async def test_extract_technical_skills_delegates_to_pipeline(monkeypatch):
    # Arrange
    captured_args = {}

    async def _fake_pipeline(content, doc_type, max_retries):
        captured_args["content"] = content
        captured_args["doc_type"] = doc_type
        captured_args["max_retries"] = max_retries
        return [{"skill": "Python"}]

    # The tool imports run_technical_skills_pipeline lazily (see module docstring on
    # why), so the fake must be patched on its source package, not on the tool module.
    monkeypatch.setattr(
        pipeline_module, "run_technical_skills_pipeline", _fake_pipeline
    )

    # Act
    result = await extract_technical_skills("some resume text", "resume", max_retries=3)

    # Assert
    assert result == [{"skill": "Python"}]
    assert captured_args == {
        "content": "some resume text",
        "doc_type": "resume",
        "max_retries": 3,
    }


async def test_extract_technical_skills_uses_default_max_retries(monkeypatch):
    # Arrange
    async def _fake_pipeline(content, doc_type, max_retries):
        return [{"max_retries_seen": max_retries}]

    monkeypatch.setattr(
        pipeline_module, "run_technical_skills_pipeline", _fake_pipeline
    )

    # Act
    result = await extract_technical_skills("text", "job_posting")

    # Assert
    assert result == [{"max_retries_seen": 2}]
