import argparse

from mcp_skills_extractor_agents.server import run_server


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp_skills_extractor_agents",
        description="Run the Candidate Skill Agent MCP server over the selected transport protocol.",
    )
    parser.add_argument(
        "--protocol",
        choices=("stdio", "http", "sse"),
        default="stdio",
        help="Transport protocol used to serve the MCP server (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for http/sse transports (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for http/sse transports (default: 8000).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_server(protocol=args.protocol, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
