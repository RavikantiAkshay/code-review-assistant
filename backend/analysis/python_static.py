from typing import List, Dict
import subprocess
import logging
import sys

logger = logging.getLogger(__name__)

# Try to import radon, but don't fail if not available
try:
    from radon.complexity import cc_visit
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False
    logger.warning("Radon not available, skipping complexity analysis")

# -----------------------------
# 1️⃣ Flake8 analysis
# -----------------------------
def analyze_python_file(file_path: str) -> List[Dict]:
    """Run flake8 on a Python file and return issues."""
    # Use sys.executable to run flake8 as a module to avoid PATH issues
    cmd = [
        sys.executable, "-m", "flake8",
        file_path,
        "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        logger.warning(f"Flake8 timed out for {file_path}")
        return []
    except FileNotFoundError:
        logger.warning("Flake8 not found in PATH")
        return []
    except Exception as e:
        logger.warning(f"Flake8 error for {file_path}: {e}")
        return []
    
    issues = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 4)
        if len(parts) != 5:
            continue
        f, row, col, code, text = parts
        try:
            issues.append({
                "tool": "flake8",
                "file": f,
                "line": int(row),
                "column": int(col),
                "code": code,
                "message": text.strip(),
                "severity": "medium"
            })
        except ValueError:
            continue
    
    logger.info(f"Flake8 found {len(issues)} issues in {file_path}")
    return issues

# -----------------------------
# 2️⃣ Radon Cyclomatic Complexity
# -----------------------------
def analyze_cyclomatic_complexity(file_path: str) -> List[Dict]:
    """Analyze cyclomatic complexity using radon."""
    if not RADON_AVAILABLE:
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return []

    issues = []
    try:
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
    except Exception as e:
        logger.warning(f"Radon error for {file_path}: {e}")
    
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
    """Run all Python analysis and return normalized issues."""
    flake_issues = analyze_python_file(file_path)
    radon_issues = analyze_cyclomatic_complexity(file_path)

    normalized = [normalize_flake8_issue(i) for i in flake_issues] + \
                 [normalize_radon_issue(i) for i in radon_issues]

    logger.info(f"Python analysis found {len(normalized)} total issues in {file_path}")
    return normalized

