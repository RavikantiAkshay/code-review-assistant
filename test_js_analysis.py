from backend.analysis.javascript_static import analyze_js_file_normalized

file_path = "test.js"  # your JS file with errors

if __name__ == "__main__":
    issues = analyze_js_file_normalized(file_path)
    print("=== ESLint JS Issues ===")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue['file']}:{issue['line']}:{issue.get('column', '')} "
              f"[{issue['code']}] {issue['message']} (severity: {issue['severity']})")
    print("\n=== Total Issues ===")
    print(len(issues))
