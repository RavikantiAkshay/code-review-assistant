import json
import logging
import os
import time
from typing import Dict

from groq import Groq
from groq import (
    APITimeoutError,
    RateLimitError,
    APIConnectionError,
    InternalServerError,
)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_FILE_BYTES = 50_000
MAX_PROMPT_CHARS = 12_000

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


def review_file_with_llm(
    file_path: str,
    language: str,
    file_content: str,
) -> Dict:

    if len(file_content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("File too large for LLM review")

    prompt = f"""
You are a strict senior code reviewer.

Review the following file and identify issues in these categories only:
- correctness
- security
- complexity
- readability
- tests

Rules:
- Return ONLY valid JSON
- No explanations, no markdown, no extra text
- Follow the schema exactly
- If a category has no issues, return an empty array
- Severity must be one of: low, medium, high
- Use line numbers from the file when possible

JSON schema:
{{
  "file": "<string>",
  "reviews": {{
    "correctness": [],
    "security": [],
    "complexity": [],
    "readability": [],
    "tests": []
  }}
}}

File path: {file_path}
Language: {language}

File content:
{file_content}
""".strip()

    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("Prompt too large for LLM")

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

        if attempt > MAX_RETRIES:
            logger.critical("LLM failed after %d retries", MAX_RETRIES)
            raise RuntimeError("LLM request failed after retries")

        time.sleep(backoff)
        backoff *= 2

    raw_output = response.choices[0].message.content.strip()

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        logger.error("Invalid JSON returned by LLM:\n%s", raw_output)
        raise ValueError("LLM returned invalid JSON")
