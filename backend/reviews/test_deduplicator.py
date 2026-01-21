from backend.reviews.deduplicator import deduplicate_reviews


def main():
    static_reviews = {
        "correctness": [
            {
                "line": 10,
                "severity": "medium",
                "message": "Hook called conditionally",
                "rule": None,
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
            }
        ],
        "readability": [],
        "security": [],
        "complexity": [],
        "tests": [],
    }

    result = deduplicate_reviews(
        file="test.js",
        static_reviews=static_reviews,
        llm_reviews=llm_reviews,
    )

    print(result)


if __name__ == "__main__":
    main()
