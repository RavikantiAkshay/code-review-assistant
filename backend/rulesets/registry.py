RULESETS = {
    "pep8": {
        "name": "PEP 8 – Python Style Guide",
        "description": "Official Python style guide for readable, consistent Python code.",
        "link": "https://peps.python.org/pep-0008/",
        "language": "python",
        "categories": ["readability", "complexity"],
        "rules": [
            {
                "id": "PEP8-E302",
                "description": "Expected 2 blank lines between top-level definitions",
                "severity": "low",
                "link": "https://peps.python.org/pep-0008/#blank-lines",
            },
            {
                "id": "PEP8-E501",
                "description": "Line too long (>79 characters)",
                "severity": "medium",
                "link": "https://peps.python.org/pep-0008/#maximum-line-length",
            },
        ],
    },

    "owasp-top-10": {
        "name": "OWASP Top 10",
        "description": "Top 10 most critical web application security risks.",
        "link": "https://owasp.org/Top10/",
        "language": "any",
        "categories": ["security"],
        "rules": [
            {
                "id": "A01",
                "description": "Broken Access Control",
                "severity": "high",
                "link": "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
            },
            {
                "id": "A03",
                "description": "Injection",
                "severity": "high",
                "link": "https://owasp.org/Top10/A03_2021-Injection/",
            },
        ],
    },

    "react-hooks": {
        "name": "React Hooks Rules",
        "description": "Rules that ensure correct usage of React Hooks.",
        "link": "https://react.dev/reference/rules/rules-of-hooks",
        "language": "javascript",
        "categories": ["correctness"],
        "rules": [
            {
                "id": "RH-01",
                "description": "Hooks must be called at the top level",
                "severity": "high",
                "link": "https://react.dev/reference/rules/rules-of-hooks",
            },
            {
                "id": "RH-02",
                "description": "Hooks must be called from React function components or custom hooks",
                "severity": "high",
                "link": "https://react.dev/reference/rules/rules-of-hooks",
            },
        ],
    },
}
