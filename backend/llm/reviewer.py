import json
from typing import Dict
from groq import Groq
import os

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def review_file_with_llm(
    file_path: str,
    language: str,
    file_content: str
) -> Dict:
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

    messages = [
        {
            "role": "system",
            "content": "You are a strict senior code reviewer."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]


    response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=messages,
    temperature=0,
    )   


    raw_output = response.choices[0].message.content.strip()

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid JSON")
