from pathlib import Path

PROMPT_PATH = Path(__file__).parent / "prompts" / "code_review.txt"

def build_review_prompt(file_path: str, language: str, code: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{{file_path}}", file_path)
        .replace("{{language}}", language)
        .replace("{{code}}", code)
    )
