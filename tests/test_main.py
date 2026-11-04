"""Tests for the CLI entrypoint."""

from mcp_skills_extractor_agents import main as module
from mcp_skills_extractor_agents.main import main


def _mock_run_server(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        module,
        "run_server",
        lambda protocol, host, port: calls.append(
            {"protocol": protocol, "host": host, "port": port}
        ),
    )
    return calls


def test_main_uses_default_protocol_host_and_port(monkeypatch):
    # Arrange
    calls = _mock_run_server(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mcp_skills_extractor_agents"])

    # Act
    main()

    # Assert
    assert calls == [{"protocol": "stdio", "host": "127.0.0.1", "port": 8000}]


def test_main_forwards_explicit_protocol_host_and_port(monkeypatch):
    # Arrange
    calls = _mock_run_server(monkeypatch)
    monkeypatch.setattr(
        "sys.argv",
        [
            "mcp_skills_extractor_agents",
            "--protocol",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ],
    )

    # Act
    main()

    # Assert
    assert calls == [{"protocol": "http", "host": "0.0.0.0", "port": 9000}]
