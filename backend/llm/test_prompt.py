from backend.llm.review_engine import build_review_prompt

code = "var x = 1\nconsole.log(x)\n"
prompt = build_review_prompt(
    file_path="test.js",
    language="javascript",
    code=code
)

print(prompt)
