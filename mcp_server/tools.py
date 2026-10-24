import os
import re
import tempfile
import logging
from typing import Dict, Any, List, Optional

from backend.analysis.ast_engine import analyze_code_ast, extract_ast_symbols, get_language_for_file
from backend.analysis.python_static import analyze_python_file_normalized
from backend.analysis.javascript_static import analyze_js_file_normalized
from backend.reviews.deduplicator import deduplicate_reviews, resolve_rule_category
from backend.reviews.ranking import rank_reviews
from backend.llm.reviewer import review_file_with_llm

logger = logging.getLogger("mcp_server.tools")


def parse_unified_diff(diff_text: str) -> Dict[str, List[Dict[str, int]]]:
    """
    Parse a unified diff string to extract affected files and modified line ranges.
    Returns: { "path/to/file": [ {"start": 10, "end": 18}, ... ] }
    """
    modified_ranges: Dict[str, List[Dict[str, int]]] = {}
    current_file = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in modified_ranges:
                modified_ranges[current_file] = []
        elif line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            current_file = line[4:].strip()
            if current_file.startswith("b/"):
                current_file = current_file[2:]
            if current_file not in modified_ranges:
                modified_ranges[current_file] = []
        elif line.startswith("@@ ") and current_file:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start_line = int(match.group(1))
                line_count = int(match.group(2)) if match.group(2) else 1
                end_line = start_line + max(line_count - 1, 0)
                modified_ranges[current_file].append({
                    "start": start_line,
                    "end": end_line,
                })

    return modified_ranges


def execute_file_review(
    file_path: str,
    content: Optional[str] = None,
    ruleset: Optional[str] = None,
    repo_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Core review logic combining AST analysis, static analysis, and LLM review.
    """
    resolved_path = file_path
    if repo_path and not os.path.isabs(file_path):
        resolved_path = os.path.join(repo_path, file_path)

    # Read content from file if not provided
    if content is None:
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"File not found: {resolved_path}")
        with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

    language = get_language_for_file(file_path)
    if not language:
        return {
            "file": file_path,
            "error": f"Unsupported file type: {file_path}",
            "issues": [],
            "summary": {"total_issues": 0},
        }

    static_reviews: Dict[str, List[Dict[str, Any]]] = {
        "correctness": [],
        "security": [],
        "complexity": [],
        "readability": [],
        "tests": [],
    }

    # 1. Deterministic AST Analysis
    try:
        ast_findings = analyze_code_ast(file_path, content, language)
        for issue in ast_findings:
            issue["file"] = file_path
            cat = issue.get("category", "correctness").lower()
            if cat in static_reviews:
                static_reviews[cat].append(issue)
            else:
                static_reviews["correctness"].append(issue)
    except Exception as e:
        logger.warning(f"AST analysis error for {file_path}: {e}")

    # 2. Static Linters
    temp_target = None
    target_disk_path = resolved_path

    if not os.path.exists(resolved_path) or content is not None:
        temp_dir = tempfile.mkdtemp()
        suffix = os.path.splitext(file_path)[1]
        temp_target = os.path.join(temp_dir, f"temp_review{suffix}")
        with open(temp_target, "w", encoding="utf-8") as f:
            f.write(content)
        target_disk_path = temp_target

    try:
        linter_issues: List[Dict[str, Any]] = []
        if language == "python":
            linter_issues = analyze_python_file_normalized(target_disk_path)
        elif language in ("javascript", "jsx", "typescript", "ts", "tsx"):
            linter_issues = analyze_js_file_normalized(target_disk_path)

        for issue in linter_issues:
            issue["file"] = file_path
            rule_code = issue.get("code")
            mapped_cat = resolve_rule_category(rule_code)
            if mapped_cat and mapped_cat in static_reviews:
                static_reviews[mapped_cat].append(issue)
            elif issue.get("type") == "complexity":
                static_reviews["complexity"].append(issue)
            else:
                static_reviews["readability"].append(issue)
    except Exception as e:
        logger.warning(f"Static linter error for {file_path}: {e}")
    finally:
        if temp_target and os.path.exists(temp_target):
            try:
                os.remove(temp_target)
                os.rmdir(os.path.dirname(temp_target))
            except Exception:
                pass

    # 3. LLM Review (if API key present)
    llm_reviews: Dict[str, List[Dict[str, Any]]] = {
        cat: [] for cat in static_reviews.keys()
    }
    if os.environ.get("GROQ_API_KEY"):
        try:
            llm_result = review_file_with_llm(
                file_path=file_path,
                language=language,
                file_content=content,
                ruleset=ruleset,
            )
            for cat in llm_reviews.keys():
                if cat in llm_result.get("reviews", {}):
                    for issue in llm_result["reviews"][cat]:
                        issue["file"] = file_path
                        llm_reviews[cat].append(issue)
        except Exception as e:
            logger.warning(f"LLM review failed for {file_path}: {e}")

    # 4. Deduplicate and Rank
    merged_reviews = deduplicate_reviews(
        file=file_path,
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )
    ranked = rank_reviews(merged_reviews)
    for issue in ranked:
        issue["file"] = file_path

    summary = {
        "total_issues": len(ranked),
        "high_severity": len([i for i in ranked if i.get("severity") == "high"]),
        "medium_severity": len([i for i in ranked if i.get("severity") == "medium"]),
        "low_severity": len([i for i in ranked if i.get("severity") == "low"]),
        "security_issues": len([i for i in ranked if i.get("category") == "security"]),
        "correctness_issues": len([i for i in ranked if i.get("category") == "correctness"]),
    }

    return {
        "file": file_path,
        "language": language,
        "summary": summary,
        "ranked_issues": ranked,
    }


def execute_diff_review(
    diff: str,
    repo_path: Optional[str] = None,
    ruleset: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Review code changes in a git unified diff, focusing exclusively on changed lines.
    """
    modified_ranges = parse_unified_diff(diff)
    if not modified_ranges:
        return {
            "message": "No modified files or hunks detected in diff.",
            "files_reviewed": 0,
            "issues": [],
        }

    all_diff_issues: List[Dict[str, Any]] = []
    files_reviewed = []

    for file_path, hunks in modified_ranges.items():
        try:
            review_res = execute_file_review(
                file_path=file_path,
                ruleset=ruleset,
                repo_path=repo_path,
            )
            files_reviewed.append(file_path)

            for issue in review_res.get("ranked_issues", []):
                issue_line = issue.get("line")
                if issue_line is None:
                    continue

                in_hunk = any(
                    (hunk["start"] - 2) <= issue_line <= (hunk["end"] + 2)
                    for hunk in hunks
                )
                if in_hunk:
                    issue["diff_hunk_match"] = True
                    all_diff_issues.append(issue)

        except Exception as e:
            logger.warning(f"Error reviewing diff file {file_path}: {e}")

    all_diff_issues.sort(key=lambda x: x.get("impact", 0), reverse=True)

    return {
        "files_reviewed": len(files_reviewed),
        "files": files_reviewed,
        "diff_issues_count": len(all_diff_issues),
        "issues": all_diff_issues,
    }


def execute_get_ast_symbols(file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract AST symbols, function/class hierarchy, complexity, and imports.
    """
    if content is None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

    language = get_language_for_file(file_path)
    if not language:
        return {"error": f"Unsupported language for file: {file_path}"}

    return extract_ast_symbols(file_path, content, language)


def execute_get_file_metrics(file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate code metrics: lines of code, cyclomatic complexity, and maintainability index.
    """
    if content is None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

    lines = content.splitlines()
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())
    comment_lines = sum(1 for line in lines if line.strip().startswith(("#", "//", "/*", "*")))
    code_lines = total_lines - blank_lines - comment_lines

    metrics: Dict[str, Any] = {
        "file_path": file_path,
        "lines": {
            "total": total_lines,
            "code": code_lines,
            "comment": comment_lines,
            "blank": blank_lines,
        },
    }

    language = get_language_for_file(file_path)
    metrics["language"] = language

    # Compute Python Radon metrics
    if language == "python":
        try:
            from radon.complexity import cc_visit
            from radon.metrics import mi_visit

            blocks = cc_visit(content)
            complexities = [b.complexity for b in blocks]
            avg_cc = round(sum(complexities) / len(complexities), 2) if complexities else 1.0
            max_cc = max(complexities) if complexities else 1
            mi_score = round(mi_visit(content, multi=False), 2)

            metrics["complexity"] = {
                "average_cyclomatic_complexity": avg_cc,
                "max_cyclomatic_complexity": max_cc,
                "maintainability_index": mi_score,
                "total_blocks": len(blocks),
            }
        except Exception as e:
            metrics["complexity_error"] = str(e)
    else:
        # Generic JS/JSX symbol-based metrics
        symbols = extract_ast_symbols(file_path, content, language)
        functions = symbols.get("functions", [])
        complexities = [f.get("complexity", 1) for f in functions if isinstance(f, dict)]
        avg_cc = round(sum(complexities) / len(complexities), 2) if complexities else 1.0

        metrics["complexity"] = {
            "average_cyclomatic_complexity": avg_cc,
            "functions_count": len(functions),
            "classes_count": len(symbols.get("classes", [])),
            "imports_count": len(symbols.get("imports", [])),
        }

    return metrics
