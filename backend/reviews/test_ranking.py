from backend.reviews.ranking import rank_reviews


def main():
    reviews = {
        "correctness": [
            {
                "line": 10,
                "severity": "high",
                "message": "Hooks must be called at the top level",
                "rule": {"id": "RH-01", "link": "https://react.dev/reference/rules/rules-of-hooks"},
                "source": "llm",
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
        "security": [],
        "complexity": [],
        "tests": [],
    }

    ranked = rank_reviews(reviews)

    for r in ranked:
        print(r)


if __name__ == "__main__":
    main()
