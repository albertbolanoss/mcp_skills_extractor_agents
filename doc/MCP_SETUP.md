# MCP Settings

## Debug MCP Server

The MCP Inspector (`mcp dev`) is the easiest way to debug. It launches a web UI where you
can list and call tools/prompts. Requires `mcp[cli]` (already a dependency) and Node.js
installed.

Adjust host/port in the URL to match the `--host`/`--port` you passed to the server.

### stdio

For stdio you don't start the server yourself — the Inspector spawns it and connects over
stdio automatically. Nothing to configure in the UI:

```sh
uv run mcp dev src/mcp_skills_extractor_agents/server/mcp_server.py
```

### streamable HTTP

1. Start the server in one terminal:

   ```sh
   uv run python -m mcp_skills_extractor_agents.main --protocol http --port 8000
   ```
2. Open the Inspector in another terminal:

   ```sh
   npx @modelcontextprotocol/inspector
   ```
3. In the Inspector UI, set these parameters and press **Connect**:

   - **Transport Type:** `Streamable HTTP`
   - **URL:** `http://127.0.0.1:8000/mcp`  ← must end in `/mcp`, **not** `/sse`

Quick smoke test with curl (initialize handshake, expects HTTP 200):

```sh
curl -i -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

### SSE (legacy)

1. Start the server in one terminal:

   ```sh
   uv run python -m mcp_skills_extractor_agents.main --protocol sse --port 8000
   ```
2. Open the Inspector in another terminal:

   ```sh
   npx @modelcontextprotocol/inspector
   ```
3. In the Inspector UI, set these parameters and press **Connect**:

   - **Transport Type:** `SSE`
   - **URL:** `http://127.0.0.1:8000/sse`  ← must end in `/sse`

Quick smoke test with curl (opens the SSE stream, expects HTTP 200):

```sh
curl -i -N http://127.0.0.1:8000/sse
```

### Model context protocol Inspector (Web UI)

> **Important:** in the Inspector the **Transport Type must match the `--protocol` the
> server was started with**, and the **URL must use that protocol's path**. Each transport
> serves on a different path, so mixing them (e.g. Streamable HTTP + a `/sse` URL) returns
> `404 Not Found`.

| Server started with  | Inspector — Transport Type | Inspector — URL              | Path     |
| -------------------- | --------------------------- | ----------------------------- | -------- |
| `--protocol stdio` | STDIO (auto via`mcp dev`) | n/a (Inspector spawns it)     | n/a      |
| `--protocol http`  | **Streamable HTTP**   | `http://127.0.0.1:8000/mcp` | `/mcp` |
| `--protocol sse`   | **SSE**               | `http://127.0.0.1:8000/sse` | `/sse` |

### Trying the tools/prompts in the Inspector

1. Connect (any transport above), open the **Tools** tab, click **List Tools** — you should
   see `extract_technical_skills`, `extract_soft_skills`, `extract_certifications`,
   `extract_languages`.
2. Call each `extract_*` tool with any `resume_path` string (they're mocked — the path isn't
   actually read).
3. Open the **Prompts** tab, click **List Prompts**, then **Get Prompt** for
   `coordinator_orchestration` to see the full system-prompt text it returns.

## Register MCP Server for claude code

```sh
# Sintaxis general:
claude mcp add <nombre> <comando> [args...] --scope <local|project|user>

# Install mcp-skills-extractor-agents (local dev, from this checkout)
claude mcp add mcp-skills-extractor-agents --scope project -- \
    uv --directory /path/to/mcp-skills-extractor-agents run \
    python -m mcp_skills_extractor_agents.main --protocol stdio

# Stdio Server (local process, the most common):
claude mcp add airbnb -- npx -y @openbnb/mcp-server-airbnb
claude mcp add mi-server -e API_KEY=abc123 -- npx -y algun-paquete

#  Remote Server (HTTP / SSE):
claude mcp add --transport http mi-server https://ejemplo.com/mcp
claude mcp add --transport sse  mi-server https://ejemplo.com/sse
# With headers (auth)
  claude mcp add --transport http mi-server https://ejemplo.com/mcp \
    --header "Authorization: Bearer TOKEN"

## Other commands
claude mcp list                     # List mcp servers
claude mcp get <name>               # Check mcp server
claude mcp remove <name>            # Delete mcp server
claude mcp add-json <name> '<json>' # Add mcp server using Json
```

### .mcp.json example for claude code (local dev, no publish needed)

```json
{
  "mcpServers": {
    "mcp-skills-extractor-agents": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_skills_extractor_agents.main", "--protocol", "stdio"]
    }
  }
}
```

This is exactly what's in this repo's own `.mcp.json` — running `claude mcp list` from this
directory (or just opening Claude Code here) should already pick it up at `project` scope.

### Manually

Claude Code has 3 scopes:

| Scope           | Flag            | Path                                  | Availability                     |
| --------------- | --------------- | ------------------------------------- | -------------------------------- |
| local (default) | --scope local   | ~/.claude.json (this project section) | Only you, only in this project   |
| project         | --scope project | .mcp.json (project root)              | Anyone who clones the repo (git) |
| user            | --scope user    | ~/.claude.json (global section)       | You, across all your projects    |

Precedence when a name repeats: local > project > user.
The `mcpServers` JSON block goes inside the file for each scope.

## Install MCP server to Claude Desktop

#### Adding the MCP server to json configuration:

Edit the file **C:\Users\[USER]\AppData\Roaming\Claude\claude_desktop_config.json**
or use **%APPDATA%\Claude\claude_desktop_config.json**

```json
{
  "mcpServers": {
    "mcp-skills-extractor-agents": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\mcp-skills-extractor-agents", "run", "python", "-m", "mcp_skills_extractor_agents.main", "--protocol", "stdio"]
    }
  }
}
```

Once this project is published (see `MCP.md`), the same config can switch to `uvx` the way
`labs_mcp_server`'s `SETUP.md` documents for `weather`.
