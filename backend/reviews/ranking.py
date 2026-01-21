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
    severity = issue["severity"]
    source = issue.get("source", "llm")  # default llm

    severity_score = SEVERITY_WEIGHT[severity]
    confidence = 1.0 if source == "llm" else 0.7
    reach = CATEGORY_REACH.get(category, 1.0)

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
