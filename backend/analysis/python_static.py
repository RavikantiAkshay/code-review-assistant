from typing import List, Dict
import subprocess
from radon.complexity import cc_visit

# -----------------------------
# 1️⃣ Flake8 analysis
# -----------------------------
def analyze_python_file(file_path: str) -> List[Dict]:
    cmd = [
        "flake8",
        file_path,
        "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    issues = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 4)
        if len(parts) != 5:
            continue
        f, row, col, code, text = parts
        issues.append({
            "tool": "flake8",
            "file": f,
            "line": int(row),
            "column": int(col),
            "code": code,
            "message": text.strip(),
            "severity": "medium"
        })
    return issues

# -----------------------------
# 2️⃣ Radon Cyclomatic Complexity
# -----------------------------
def analyze_cyclomatic_complexity(file_path: str) -> List[Dict]:
    with open(file_path, "r") as f:
        code = f.read()

    issues = []
    for block in cc_visit(code):
        if block.complexity > 10:
            issues.append({
                "tool": "radon",
                "file": file_path,
                "line": block.lineno,
                "name": block.name,
                "complexity": block.complexity,
                "message": f"High cyclomatic complexity ({block.complexity}) in {block.name}",
                "severity": "medium"
            })
    return issues

# -----------------------------
# 3️⃣ Normalization
# -----------------------------
def normalize_flake8_issue(flake_issue: Dict) -> Dict:
    return {
        "tool": flake_issue["tool"],
        "file": flake_issue["file"],
        "line": flake_issue["line"],
        "column": flake_issue.get("column", None),
        "code": flake_issue.get("code", ""),
        "message": flake_issue["message"],
        "severity": flake_issue["severity"],
        "type": "syntax"
    }

def normalize_radon_issue(radon_issue: Dict) -> Dict:
    return {
        "tool": radon_issue["tool"],
        "file": radon_issue["file"],
        "line": radon_issue["line"],
        "column": None,
        "code": "CC",
        "message": radon_issue["message"],
        "severity": radon_issue["severity"],
        "type": "complexity"
    }

def analyze_python_file_normalized(file_path: str) -> List[Dict]:
    flake_issues = analyze_python_file(file_path)
    radon_issues = analyze_cyclomatic_complexity(file_path)

    normalized = [normalize_flake8_issue(i) for i in flake_issues] + \
                 [normalize_radon_issue(i) for i in radon_issues]

    return normalized
