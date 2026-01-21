import json
import logging
import os
import time
import re
from typing import Dict

from groq import Groq
from groq import (
    APITimeoutError,
    RateLimitError,
    APIConnectionError,
    InternalServerError,
)

from backend.rulesets.registry import RULESETS

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
MAX_FILE_BYTES = 50_000
MAX_PROMPT_CHARS = 12_000

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


JSON_SCHEMA = """
{
  "file": "<string>",
  "reviews": {
    "correctness": [
      {
        "line": <number>,
        "severity": "<low|medium|high>",
        "message": "<string>",
        "rule": {
          "id": "<string>",
          "link": "<string>"
        } | null
      }
    ],
    "security": [],
    "complexity": [],
    "readability": [],
    "tests": []
  }
}
""".strip()


def review_file_with_llm(
    file_path: str,
    language: str,
    file_content: str,
    ruleset: str | None = None,
) -> Dict:

    if ruleset and ruleset not in RULESETS:
        raise ValueError(f"Unknown ruleset: {ruleset}")

    if len(file_content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("File too large for LLM review")

    ruleset_block = ""

    if ruleset:
        rs = RULESETS[ruleset]

        rules_lines = []
        for r in rs["rules"]:
            rules_lines.append(
                f"- ID: {r['id']}\n"
                f"  Description: {r['description']}\n"
                f"  Severity: {r['severity']}\n"
                f"  Reference: {r['link']}"
            )

        rules_text = "\n".join(rules_lines)

        ruleset_block = (
            "Active ruleset:\n"
            f"Name: {rs['name']}\n"
            f"Applicable categories: {', '.join(rs['categories'])}\n\n"
            "Enforced rules (use ONLY these):\n"
            f"{rules_text}"
        )

    prompt = f"""
You are a strict senior code reviewer.

{ruleset_block}

Review the following file and report issues in these categories ONLY:
- correctness
- security
- complexity
- readability
- tests

ABSOLUTE RULES:
- Return ONE JSON OBJECT (not an array)
- Return ONLY valid JSON, no text outside it
- Follow the schema EXACTLY
- Do NOT add extra keys
- Each issue object MUST contain ONLY:
  - line (number)
  - severity ("low" | "medium" | "high")
  - message (non-empty string)
- If a category has no issues, return an empty array
- If an issue matches an enforced rule, you MUST:
  - include the rule ID and link inside the "rule" object
- If no rule applies, set "rule" to null
- NEVER mention rule IDs or links inside "message"

JSON schema:
{JSON_SCHEMA}

File path: {file_path}

File content:
{file_content}
""".strip()

    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("Prompt too large")

    messages = [
        {"role": "system", "content": "You are a strict senior code reviewer."},
        {"role": "user", "content": prompt},
    ]

    attempt = 0
    backoff = INITIAL_BACKOFF

    while True:
        try:
            logger.info("LLM request attempt %d for %s", attempt + 1, file_path)

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                timeout=30,
            )
            break

        except (APITimeoutError, RateLimitError) as e:
            attempt += 1
            logger.warning("Retryable LLM error: %s", e)

        except (APIConnectionError, InternalServerError) as e:
            attempt += 1
            logger.error("LLM backend error: %s", e)

        if attempt >= MAX_RETRIES:
            raise RuntimeError("LLM request failed after retries")

        time.sleep(backoff)
        backoff *= 2

    raw_output = response.choices[0].message.content.strip()

    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if not match:
        logger.error("No JSON object found in LLM output:\n%s", raw_output)
        raise ValueError("LLM returned invalid JSON")

    json_text = match.group(0)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        logger.error("Extracted JSON is invalid:\n%s", json_text)
        raise ValueError("LLM returned invalid JSON")

    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")

    if "file" not in parsed or "reviews" not in parsed:
        raise ValueError("Invalid schema returned by LLM")

    return parsed
