from backend.analysis.python_static import analyze_python_file_normalized

file_path = "backend/main.py"

issues = analyze_python_file_normalized(file_path)

print("=== Combined Normalized Issues ===")
for i in issues:
    print(i)
