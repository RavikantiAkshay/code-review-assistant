import json
import subprocess
import sys
import os

def test_mcp_server_stdio():
    """
    Subprocess test interacting with mcp_server/server.py via stdio JSON-RPC 2.0.
    """
    cmd = [sys.executable, "-m", "mcp_server.server"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        bufsize=1,
    )

    def send_rpc(msg: dict) -> dict:
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        assert line, "No response from MCP server"
        return json.loads(line.strip())

    try:
        # 1. Test initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        init_res = send_rpc(init_req)
        assert init_res.get("id") == 1
        result = init_res.get("result", {})
        assert result.get("serverInfo", {}).get("name") == "code-review-assistant"
        assert "tools" in result.get("capabilities", {})

        # 2. Test notifications/initialized
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        # 3. Test tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        list_res = send_rpc(list_req)
        assert list_res.get("id") == 2
        tools = list_res.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "review_file" in tool_names
        assert "review_diff" in tool_names
        assert "get_ast_symbols" in tool_names
        assert "get_file_metrics" in tool_names

        # 4. Test get_ast_symbols call
        sample_code = "def authenticate(user, pwd=[]):\n    except_bare = True\n    return user\n"
        call_symbols = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_ast_symbols",
                "arguments": {
                    "file_path": "sample.py",
                    "content": sample_code
                }
            }
        }
        res_symbols = send_rpc(call_symbols)
        assert res_symbols.get("id") == 3
        text_content = res_symbols["result"]["content"][0]["text"]
        parsed_symbols = json.loads(text_content)
        assert "symbols" in parsed_symbols
        assert parsed_symbols["symbols"][0]["name"] == "authenticate"

        # 5. Test get_file_metrics call
        call_metrics = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_file_metrics",
                "arguments": {
                    "file_path": "sample.py",
                    "content": sample_code
                }
            }
        }
        res_metrics = send_rpc(call_metrics)
        assert res_metrics.get("id") == 4
        metrics = json.loads(res_metrics["result"]["content"][0]["text"])
        assert "lines" in metrics
        assert metrics["lines"]["total"] == 3

        # 6. Test review_file call (AST anti-pattern check)
        call_review = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "review_file",
                "arguments": {
                    "file_path": "sample.py",
                    "content": "def bad(x=[]):\n    try:\n        eval(x)\n    except:\n        pass\n"
                }
            }
        }
        res_review = send_rpc(call_review)
        assert res_review.get("id") == 5
        review_data = json.loads(res_review["result"]["content"][0]["text"])
        assert "ranked_issues" in review_data
        assert review_data["summary"]["total_issues"] >= 3

        # 7. Test review_diff call
        diff_text = """--- a/src/auth.py
+++ b/src/auth.py
@@ -10,3 +10,4 @@
 def query_user(user_id):
+    eval(user_id)
     return True
"""
        call_diff = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "review_diff",
                "arguments": {
                    "diff": diff_text,
                    "repo_path": "evaluation/seed_repo"
                }
            }
        }
        res_diff = send_rpc(call_diff)
        assert res_diff.get("id") == 6
        diff_data = json.loads(res_diff["result"]["content"][0]["text"])
        assert "diff_issues_count" in diff_data

    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


if __name__ == "__main__":
    test_mcp_server_stdio()
    print("All MCP server JSON-RPC 2.0 stdio tests passed successfully!")
