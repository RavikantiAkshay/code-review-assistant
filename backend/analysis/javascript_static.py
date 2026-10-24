import subprocess
import json
from typing import List, Dict

def analyze_js_file(file_path: str) -> List[Dict]:
    """
    Run ESLint on a single JS file and return a list of issues.
    Each issue is a dict with keys: file, line, column, code, message, severity
    """
    # Run ESLint in JSON output mode
    # --no-ignore: Allow linting files outside base path (temp directories)
    # --no-eslintrc: Use default rules if no config found
    cmd = [
        "npx.cmd", "eslint", file_path, 
        "--format", "json",
        "--no-ignore",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=None)
    issues: List[Dict] = []

    # ESLint exit codes: 0=no errors, 1=errors found, 2=fatal error
    if result.returncode == 2:
        # Log error but don't raise - allow review to continue
        print(f"ESLint warning: {result.stderr}")
        return issues

    try:
        eslint_output = json.loads(result.stdout)
    except json.JSONDecodeError:
        return issues

    for file_report in eslint_output:
        for msg in file_report.get("messages", []):
            rule_id = msg.get("ruleId") or ""
            text = msg.get("message") or ""

            # Skip CommonJS / Node environment globals false alarms
            if rule_id == "no-undef" and any(g in text for g in ["'module'", "'exports'", "'require'", "'process'"]):
                continue

            issue_line = msg.get("line")
            # Align react/prop-types to component definition header line
            if rule_id == "react/prop-types":
                try:
                    with open(file_report.get("filePath"), "r", encoding="utf-8", errors="ignore") as f:
                        src_lines = f.readlines()
                    for idx in range(min(len(src_lines) - 1, max(0, (issue_line or 1) - 1)), -1, -1):
                        line_str = src_lines[idx]
                        if ("function " in line_str or "const " in line_str) and "props" in line_str:
                            issue_line = idx + 1
                            break
                except Exception:
                    pass

            issues.append({
                "tool": "eslint",
                "file": file_report.get("filePath"),
                "line": issue_line,
                "column": msg.get("column"),
                "code": rule_id,
                "message": text,
                "severity": "medium" if msg.get("severity", 1) == 1 else "high"
            })

    return issues


# Normalization for JS (same schema as Python)
def normalize_js_issue(js_issue: Dict) -> Dict:
    return {
        "tool": js_issue["tool"],
        "file": js_issue["file"],
        "line": js_issue["line"],
        "column": js_issue.get("column", None),
        "code": js_issue.get("code", ""),
        "message": js_issue["message"],
        "severity": js_issue["severity"],
        "type": "syntax"
    }

def analyze_js_file_normalized(file_path: str) -> List[Dict]:
    raw_issues = analyze_js_file(file_path)
    return [normalize_js_issue(i) for i in raw_issues]
