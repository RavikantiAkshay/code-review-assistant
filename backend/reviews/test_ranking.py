import pytest
from backend.reviews.ranking import rank_reviews, compute_impact


def test_ranking_sort_order():
    reviews = {
        "correctness": [
            {
                "line": 10,
                "severity": "high",
                "message": "Hooks must be called at the top level",
                "rule": {"id": "RH-01", "link": "https://react.dev/reference/rules/rules-of-hooks"},
                "source": "both",
                "sources": ["static", "llm"],
            }
        ],
        "readability": [
            {
                "line": 2,
                "severity": "low",
                "message": "Missing semicolon",
                "rule": None,
                "source": "static",
            }
        ],
        "security": [
            {
                "line": 45,
                "severity": "critical",
                "message": "SQL injection via raw formatting",
                "source": "llm",
            }
        ],
        "complexity": [],
        "tests": [],
    }

    ranked = rank_reviews(reviews)

    assert len(ranked) == 3
    # Critical security (4 * 1.0 * 1.5 = 6.0) should be first
    assert ranked[0]["category"] == "security"
    assert ranked[0]["severity"] == "critical"
    assert ranked[0]["impact"] == 6.0

    # High correctness with dual source (3 * 1.0 * 1.5 = 4.5) should be second
    assert ranked[1]["category"] == "correctness"
    assert ranked[1]["impact"] == 4.5

    # Low readability (1 * 0.85 * 1.0 = 0.85) should be third
    assert ranked[2]["category"] == "readability"
    assert ranked[2]["impact"] == 0.85


def test_compute_impact_confidence():
    # Both static and LLM yields 1.0 confidence
    impact_both = compute_impact({"severity": "high", "source": "both"}, "correctness")
    assert impact_both == round(3 * 1.0 * 1.5, 2)

    # Static-only yields 0.85 confidence
    impact_static = compute_impact({"severity": "high", "source": "static"}, "correctness")
    assert impact_static == round(3 * 0.85 * 1.5, 2)


if __name__ == "__main__":
    test_ranking_sort_order()
    test_compute_impact_confidence()
    print("All ranking tests passed!")
