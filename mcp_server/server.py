import sys
import json
import logging
import traceback
from typing import Dict, Any, Optional

from mcp_server.tools import (
    execute_file_review,
    execute_diff_review,
    execute_get_ast_symbols,
    execute_get_file_metrics,
)

# Crucial: All logging must go to sys.stderr to preserve sys.stdout strictly for JSON-RPC
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [MCP] %(levelname)s: %(message)s",
)
logger = logging.getLogger("mcp_server")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "code-review-assistant"
SERVER_VERSION = "1.0.0"

TOOL_DEFINITIONS = [
    {
        "name": "review_file",
        "description": "Run comprehensive code review on a file using AST analysis, static linters, and LLM reasoning. Returns ranked findings with code fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to review (relative or absolute).",
                },
                "content": {
                    "type": "string",
                    "description": "Optional in-memory file content. If omitted, file is read from disk.",
                },
                "ruleset": {
                    "type": "string",
                    "description": "Optional ruleset to enforce: 'pep8', 'owasp_top_10', or 'react_hooks'.",
                    "enum": ["pep8", "owasp_top_10", "react_hooks"],
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository base directory if file_path is relative.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "review_diff",
        "description": "Review code modifications inside a unified git diff string. Filters issues strictly to altered or adjacent lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {
                    "type": "string",
                    "description": "Unified git diff text to analyze.",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional root directory of repository.",
                },
                "ruleset": {
                    "type": "string",
                    "description": "Optional ruleset to enforce.",
                    "enum": ["pep8", "owasp_top_10", "react_hooks"],
                },
            },
            "required": ["diff"],
        },
    },
    {
        "name": "get_ast_symbols",
        "description": "Extract AST symbols, function/class declarations, cyclomatic complexity, docstrings, and imports from a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the code file.",
                },
                "content": {
                    "type": "string",
                    "description": "Optional in-memory file content.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_file_metrics",
        "description": "Compute code health metrics including line counts, Radon cyclomatic complexity, and maintainability index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the code file.",
                },
                "content": {
                    "type": "string",
                    "description": "Optional in-memory file content.",
                },
            },
            "required": ["file_path"],
        },
    },
]


def send_response(response: Dict[str, Any]):
    """Write single-line JSON-RPC response to stdout and flush."""
    line = json.dumps(response) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def handle_initialize(req_id: Any, params: Dict[str, Any]):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        },
    }


def handle_tools_list(req_id: Any):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": TOOL_DEFINITIONS,
        },
    }


def handle_tools_call(req_id: Any, params: Dict[str, Any]):
    tool_name = params.get("name")
    args = params.get("arguments", {})

    logger.info(f"Executing tool call: {tool_name}")

    try:
        if tool_name == "review_file":
            res = execute_file_review(
                file_path=args.get("file_path"),
                content=args.get("content"),
                ruleset=args.get("ruleset"),
                repo_path=args.get("repo_path"),
            )
        elif tool_name == "review_diff":
            res = execute_diff_review(
                diff=args.get("diff"),
                repo_path=args.get("repo_path"),
                ruleset=args.get("ruleset"),
            )
        elif tool_name == "get_ast_symbols":
            res = execute_get_ast_symbols(
                file_path=args.get("file_path"),
                content=args.get("content"),
            )
        elif tool_name == "get_file_metrics":
            res = execute_get_file_metrics(
                file_path=args.get("file_path"),
                content=args.get("content"),
            )
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(res, indent=2)}],
                "isError": False,
            },
        }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}\n{traceback.format_exc()}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}],
                "isError": True,
            },
        }


def run_stdio_server():
    """Main event loop reading newline-delimited JSON-RPC from stdin."""
    logger.info(f"{SERVER_NAME} v{SERVER_VERSION} started (stdio transport)")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break  # EOF reached

            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as err:
                logger.error(f"Invalid JSON received: {err}")
                send_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                })
                continue

            method = msg.get("method")
            req_id = msg.get("id")

            # Notification methods (no id, no response expected)
            if method == "notifications/initialized":
                logger.info("Client initialization confirmed.")
                continue

            if req_id is None:
                # Other notifications
                continue

            if method == "initialize":
                resp = handle_initialize(req_id, msg.get("params", {}))
                send_response(resp)
            elif method == "tools/list":
                resp = handle_tools_list(req_id)
                send_response(resp)
            elif method == "tools/call":
                resp = handle_tools_call(req_id, msg.get("params", {}))
                send_response(resp)
            elif method == "ping":
                send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
            else:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                })

        except KeyboardInterrupt:
            logger.info("Server terminated by keyboard interrupt.")
            break
        except Exception as e:
            logger.critical(f"Unexpected loop exception: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    run_stdio_server()
