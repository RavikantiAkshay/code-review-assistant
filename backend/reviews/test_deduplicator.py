import pytest
from backend.reviews.deduplicator import (
    deduplicate_reviews,
    are_issues_duplicate,
    get_line_range,
    are_lines_proximate,
    merge_issue_pair,
)


def test_line_range_and_proximity():
    # Single line
    assert get_line_range({"line": 15}) == (15, 15)
    # Range
    assert get_line_range({"line_start": 10, "line_end": 14}) == (10, 14)
    # Swapped
    assert get_line_range({"line_start": 20, "line_end": 18}) == (18, 20)
    # Row (flake8)
    assert get_line_range({"row": 25}) == (25, 25)

    # Overlapping ranges
    assert are_lines_proximate((10, 14), (12, 16)) is True
    # Adjacent within tolerance
    assert are_lines_proximate((10, 10), (13, 13), tolerance=3) is True
    # Exceeding tolerance
    assert are_lines_proximate((10, 10), (15, 15), tolerance=3) is False


def test_cross_category_deduplication():
    """
    Test that Flake8 E722 placed in 'readability' merges cleanly with
    LLM broad exception placed in 'correctness', elevating to 'correctness'.
    """
    static_reviews = {
        "readability": [
            {
                "line": 40,
                "code": "E722",
                "severity": "medium",
                "message": "E722 do not use bare 'except'",
            }
        ],
        "correctness": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    llm_reviews = {
        "correctness": [
            {
                "line": 40,
                "severity": "high",
                "message": "Too broad exception clause can mask system errors",
                "snippet": "except:\n    pass",
                "fix": "except Exception as e:\n    logger.error(e)",
                "rule": {"id": "PEP8-E722", "link": "https://peps.python.org/pep-0008/#bare-except"},
            }
        ],
        "readability": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="src/auth.py",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    # Must be merged into 1 issue under correctness
    assert len(result["readability"]) == 0
    assert len(result["correctness"]) == 1

    merged = result["correctness"][0]
    assert merged["severity"] == "high"
    assert "static" in merged["sources"]
    assert "llm" in merged["sources"]
    assert merged["source"] == "both"
    assert merged["rule"]["id"] in ["E722", "PEP8-E722"]
    assert merged["snippet"] == "except:\n    pass"
    assert merged["fix"] is not None


def test_fuzzy_line_overlap():
    """
    Test line proximity: static flags line 14, LLM flags 13-16 for SQL injection.
    """
    static_reviews = {
        "security": [
            {
                "line": 14,
                "code": "S608",
                "severity": "high",
                "message": "Possible SQL injection detected via string format",
            }
        ],
        "correctness": [],
        "readability": [],
        "complexity": [],
        "tests": [],
    }

    llm_reviews = {
        "security": [
            {
                "line_start": 13,
                "line_end": 16,
                "severity": "high",
                "message": "Raw SQL injection vulnerability via string concatenation",
                "snippet": "query = f'SELECT * FROM users WHERE id={user_id}'",
                "fix": "query = 'SELECT * FROM users WHERE id = %s'\ncursor.execute(query, (user_id,))",
            }
        ],
        "correctness": [],
        "readability": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="src/database.py",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    assert len(result["security"]) == 1
    issue = result["security"][0]
    assert issue["source"] == "both"
    assert issue["fix"] is not None
    assert issue["line"] in [13, 14]


def test_distinct_issues_on_same_line_not_merged():
    """
    Line 20 has two completely different defects:
    1. Line too long (style/readability)
    2. SQL injection (security)
    They must NOT be merged together!
    """
    static_reviews = {
        "readability": [
            {
                "line": 20,
                "code": "E501",
                "severity": "low",
                "message": "Line too long (>79 characters)",
            }
        ],
        "correctness": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    llm_reviews = {
        "security": [
            {
                "line": 20,
                "severity": "high",
                "message": "SQL injection vulnerability via raw user query",
                "fix": "Use parameterized queries",
            }
        ],
        "correctness": [],
        "readability": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="src/models.py",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    assert len(result["readability"]) == 1
    assert len(result["security"]) == 1
    assert result["readability"][0]["code"] == "E501"
    assert "SQL injection" in result["security"][0]["message"]


def test_react_hook_rule_merge():
    """
    Test React hook rule ID and concept merge.
    """
    static_reviews = {
        "correctness": [
            {
                "line": 10,
                "severity": "medium",
                "message": "Hook called conditionally",
                "code": "react-hooks/rules-of-hooks",
            }
        ],
        "readability": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    llm_reviews = {
        "correctness": [
            {
                "line": 10,
                "severity": "high",
                "message": "Hooks must be called at the top level",
                "rule": {
                    "id": "RH-01",
                    "link": "https://react.dev/reference/rules/rules-of-hooks",
                },
                "fix": "Move useEffect to component top-level",
            }
        ],
        "readability": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="src/App.jsx",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    assert len(result["correctness"]) == 1
    issue = result["correctness"][0]
    assert issue["severity"] == "high"
    assert issue["source"] == "both"
    assert issue["rule"]["id"] in ["RH-01", "react-hooks/rules-of-hooks"]


def test_disjoint_files_and_lines_preserved():
    """Verify that unrelated issues across different lines and files remain intact."""
    static_reviews = {
        "readability": [
            {"line": 5, "code": "F401", "severity": "low", "message": "'os' imported but unused"},
            {"line": 25, "code": "W291", "severity": "low", "message": "trailing whitespace"},
        ],
        "correctness": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    llm_reviews = {
        "security": [
            {"line": 50, "severity": "high", "message": "Hardcoded JWT secret token"}
        ],
        "correctness": [],
        "readability": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="src/config.py",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    assert len(result["readability"]) == 2
    assert len(result["security"]) == 1


def test_dynamic_rule_category_resolution():
    from backend.reviews.deduplicator import resolve_rule_category

    # Flake8 Correctness / Syntax:
    assert resolve_rule_category("E999") == "correctness"  # Syntax error
    assert resolve_rule_category("E901") == "correctness"
    assert resolve_rule_category("E711") == "correctness"  # Comparison to None
    assert resolve_rule_category("E721") == "correctness"  # Comparison using type()
    assert resolve_rule_category("E722") == "correctness"  # Bare except
    assert resolve_rule_category("F821") == "correctness"  # Undefined variable
    assert resolve_rule_category("F823") == "correctness"  # Local variable referenced before assignment
    assert resolve_rule_category("F706") == "correctness"  # Return outside function
    assert resolve_rule_category("F601") == "correctness"  # Duplicate dict key

    # Flake8-Bugbear (Runtime bugs):
    assert resolve_rule_category("B006") == "correctness"  # Mutable default
    assert resolve_rule_category("B008") == "correctness"

    # Bandit Security:
    assert resolve_rule_category("S105") == "security"     # Hardcoded password
    assert resolve_rule_category("S608") == "security"     # SQL injection
    assert resolve_rule_category("S101") == "security"     # Use of assert

    # Radon / McCabe Complexity:
    assert resolve_rule_category("CC") == "complexity"
    assert resolve_rule_category("C901") == "complexity"

    # Flake8 Readability / Style:
    assert resolve_rule_category("F401") == "readability"  # Unused import
    assert resolve_rule_category("F541") == "readability"  # F-string without placeholders
    assert resolve_rule_category("E111") == "readability"  # Indentation
    assert resolve_rule_category("E225") == "readability"  # Missing whitespace
    assert resolve_rule_category("E302") == "readability"  # Blank lines
    assert resolve_rule_category("E501") == "readability"  # Line too long
    assert resolve_rule_category("W291") == "readability"  # Trailing whitespace

    # Namespaced codes (e.g. from ruleset configs):
    assert resolve_rule_category("PEP8-E722") == "correctness"
    assert resolve_rule_category("FLAKE8-F821") == "correctness"

    # ESLint rules:
    assert resolve_rule_category("no-eval") == "security"
    assert resolve_rule_category("security/detect-eval-with-expression") == "security"
    assert resolve_rule_category("react-hooks/rules-of-hooks") == "correctness"
    assert resolve_rule_category("no-undef") == "correctness"
    assert resolve_rule_category("no-unreachable") == "correctness"
    assert resolve_rule_category("complexity") == "complexity"
    assert resolve_rule_category("max-depth") == "complexity"
    assert resolve_rule_category("no-unused-vars") == "readability"
    assert resolve_rule_category("quotes") == "readability"


if __name__ == "__main__":
    test_line_range_and_proximity()
    test_cross_category_deduplication()
    test_fuzzy_line_overlap()
    test_distinct_issues_on_same_line_not_merged()
    test_react_hook_rule_merge()
    test_disjoint_files_and_lines_preserved()
    test_dynamic_rule_category_resolution()
    print("All deduplicator tests passed successfully!")
