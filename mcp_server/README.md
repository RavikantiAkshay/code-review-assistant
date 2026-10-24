# Code Review Assistant - Model Context Protocol (MCP) Server

The Code Review Assistant MCP server exposes static linters, deterministic AST anti-pattern analysis, and LLM reasoning directly to AI IDEs and agents (Cursor, Claude Desktop, Antigravity) via JSON-RPC 2.0 over standard I/O (`stdio`).

## Exposed Tools

| Tool | Description | Input Parameters |
|---|---|---|
| `review_file` | Full review combining AST analysis, linters, and LLM insights | `file_path` (required), `content` (optional), `ruleset` (optional), `repo_path` (optional) |
| `review_diff` | Review unified git diffs, scoping findings strictly to modified/adjacent lines | `diff` (required), `repo_path` (optional), `ruleset` (optional) |
| `get_ast_symbols` | Structural symbols, function/class declarations, complexity, and imports | `file_path` (required), `content` (optional) |
| `get_file_metrics` | Line counts, Radon cyclomatic complexity, maintainability index | `file_path` (required), `content` (optional) |

## Quickstart

### Running Directly via CLI

```bash
# Set PYTHONPATH and optional GROQ_API_KEY
export PYTHONPATH="."
python -m mcp_server.server
```

### Client Setup

#### 1. Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "code-review-assistant": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "path/to/CodeReviewAssistant",
        "GROQ_API_KEY": "your_groq_api_key_here"
      }
    }
  }
}
```

#### 2. Cursor IDE
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "code-review-assistant": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "path/to/CodeReviewAssistant",
        "GROQ_API_KEY": "your_groq_api_key_here"
      }
    }
  }
}
```

## Running Tests

```bash
pytest mcp_server/test_mcp_server.py -p no:cacheprovider
```
