"""Tests for the MCP server's transport dispatch."""

from mcp_skills_extractor_agents.server import mcp_server as module
from mcp_skills_extractor_agents.server.mcp_server import run_server


def _mock_mcp_run(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(module.mcp, "run", lambda **kwargs: calls.append(kwargs))
    return calls


def test_run_server_stdio_ignores_host_and_port(monkeypatch):
    # Arrange
    calls = _mock_mcp_run(monkeypatch)

    # Act
    run_server(protocol="stdio", host="0.0.0.0", port=9000)

    # Assert
    assert calls == [{"transport": "stdio"}]


def test_run_server_http_uses_streamable_http_transport(monkeypatch):
    # Arrange
    calls = _mock_mcp_run(monkeypatch)

    # Act
    run_server(protocol="http", host="0.0.0.0", port=9000)

    # Assert
    assert calls == [{"transport": "streamable-http", "host": "0.0.0.0", "port": 9000}]


def test_run_server_sse_uses_sse_transport(monkeypatch):
    # Arrange
    calls = _mock_mcp_run(monkeypatch)

    # Act
    run_server(protocol="sse", host="127.0.0.1", port=8000)

    # Assert
    assert calls == [{"transport": "sse", "host": "127.0.0.1", "port": 8000}]
