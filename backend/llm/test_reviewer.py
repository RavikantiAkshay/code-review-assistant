from backend.llm.reviewer import review_file_with_llm

if __name__ == "__main__":
    with open("test.js", "r", encoding="utf-8") as f:
        content = f.read()

    result = review_file_with_llm(
    file_path="test.js",
    language="javascript",
    file_content=content,
    ruleset="react-hooks"
    )


    print(result)
