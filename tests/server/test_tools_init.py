"""Tests for the extraction tools package's settings-driven conditional registration."""

import importlib
from types import SimpleNamespace

import candidate_skill_agent.server.tools as module
import candidate_skill_agent.settings as settings_package


def test_tools_init_skips_all_tools_when_active_tools_excludes_them(monkeypatch):
    # Arrange
    monkeypatch.setattr(
        settings_package,
        "get_skill_agent_settings",
        lambda: SimpleNamespace(active_tools=frozenset()),
    )

    try:
        # Act
        importlib.reload(module)

        # Assert
        assert module.EXTRACTION_TOOL_NAMES == ()
    finally:
        monkeypatch.undo()
        importlib.reload(module)
