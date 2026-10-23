from typing import Dict, List

SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

CATEGORY_REACH = {
    "correctness": 1.5,
    "security": 1.5,
    "complexity": 1.2,
    "readability": 1.0,
    "tests": 1.0,
}


def compute_impact(issue: Dict, category: str) -> float:
    severity = issue.get("severity", "low").lower()
    source = issue.get("source", "llm")
    sources = issue.get("sources", [])

    severity_score = SEVERITY_WEIGHT.get(severity, 1)
    if source == "both" or ("static" in sources and "llm" in sources):
        confidence = 1.0
    elif source in ["llm", "ast"]:
        confidence = 1.0
    elif "confidence" in issue and isinstance(issue["confidence"], (int, float)):
        confidence = float(issue["confidence"])
    else:
        confidence = 0.85

    reach = CATEGORY_REACH.get(category.lower(), 1.0)
    return round(severity_score * confidence * reach, 2)


def rank_reviews(reviews: Dict[str, List[Dict]]) -> List[Dict]:
    ranked = []

    for category, issues in reviews.items():
        for issue in issues:
            impact = compute_impact(issue, category)
            issue_with_score = issue.copy()
            issue_with_score["category"] = category
            issue_with_score["impact"] = impact
            ranked.append(issue_with_score)

    ranked.sort(key=lambda x: x["impact"], reverse=True)
    return ranked
