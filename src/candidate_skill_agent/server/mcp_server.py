from mcp.server import MCPServer

mcp = MCPServer("CandidateSkillAgent")

# Maps the CLI-friendly protocol names to the transport values MCPServer expects.
_TRANSPORTS = {
    "stdio": "stdio",
    "http": "streamable-http",
    "sse": "sse",
}


def run_server(
    protocol: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Run the Candidate Skill Agent MCP server over the given transport protocol.

    Args:
        protocol: one of "stdio", "http" or "sse". Defaults to "stdio".
        host: host to bind for the http/sse transports (ignored by stdio).
        port: port to bind for the http/sse transports (ignored by stdio).
    """
    # In mcp v2, host/port are run() keywords (MCPServer no longer has .settings.host/port);
    # stdio doesn't take them at all.
    if protocol == "stdio":
        mcp.run(transport=_TRANSPORTS[protocol])
        return
    mcp.run(transport=_TRANSPORTS[protocol], host=host, port=port)


# Absolute import (not relative) so this module keeps working if something points
# `mcp dev` directly at this file path instead of importing the package.
from candidate_skill_agent.server import prompts as _prompts  # noqa: F401
from candidate_skill_agent.server import resources as _resources  # noqa: F401
from candidate_skill_agent.server import tools as _tools  # noqa: F401

if __name__ == "__main__":
    run_server()
