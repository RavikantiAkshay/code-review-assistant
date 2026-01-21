import hashlib
from typing import Dict, List, Tuple

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def _issue_key(
    file: str,
    category: str,
    line_start: int,
    line_end: int,
) -> str:
    raw = f"{file}:{category}:{line_start}:{line_end}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_issue(issue: Dict) -> Tuple[int, int]:
    """
    Normalize line info.
    If only 'line' exists, treat as single-line issue.
    """
    if "line" in issue:
        return issue["line"], issue["line"]

    return issue.get("line_start", 0), issue.get("line_end", 0)


def deduplicate_reviews(
    *,
    file: str,
    static_reviews: Dict[str, List[Dict]],
    llm_reviews: Dict[str, List[Dict]],
) -> Dict[str, List[Dict]]:
    """
    Merge static + LLM reviews.
    Deduplicate by (file + line range + category).
    Keep strongest severity.
    """

    merged: Dict[str, Dict[str, Dict]] = {}

    def ingest(source_reviews: Dict[str, List[Dict]], source: str):
        for category, issues in source_reviews.items():
            merged.setdefault(category, {})

            for issue in issues:
                issue = issue.copy()
                issue["source"] = source
                
                line_start, line_end = _normalize_issue(issue)
                key = _issue_key(file, category, line_start, line_end)

                if key not in merged[category]:
                    merged[category][key] = issue
                    continue

                existing = merged[category][key]

                existing_sev = SEVERITY_RANK.get(existing["severity"], 0)
                new_sev = SEVERITY_RANK.get(issue["severity"], 0)

                if new_sev > existing_sev:
                    merged[category][key] = issue
                    continue

                if (
                    existing_sev == new_sev
                    and existing.get("rule") is None
                    and issue.get("rule") is not None
                ):
                    merged[category][key] = issue

    ingest(static_reviews, "static")
    ingest(llm_reviews, "llm")


    final: Dict[str, List[Dict]] = {}
    for category, issue_map in merged.items():
        final[category] = list(issue_map.values())

    return final
