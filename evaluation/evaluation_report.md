# Code Review Assistant - Evaluation Report

**Generated:** 2026-01-27 22:12:07

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Ground Truth Issues** | 39 |
| **Total Detected Issues** | 46 |
| **True Positives** | 27 |
| **False Positives** | 19 |
| **False Negatives** | 13 |

## Overall Performance

| Metric | Score |
|--------|-------|
| **Precision** | 58.70% |
| **Recall** | 67.50% |
| **F1-Score** | 62.79% |

## Performance by Category

| Category | Precision | Recall | F1-Score | TP | FP | FN |
|----------|-----------|--------|----------|----|----|-----|
| Security | 88.89% | 80.00% | 84.21% | 8 | 1 | 2 |
| Correctness | 50.00% | 41.67% | 45.45% | 5 | 5 | 7 |
| Complexity | 66.67% | 80.00% | 72.73% | 4 | 2 | 1 |
| Readability | 47.62% | 76.92% | 58.82% | 10 | 11 | 3 |

## Performance by Severity

| Severity | Precision | Recall | F1-Score | TP | FP | FN |
|----------|-----------|--------|----------|----|----|-----|
| High | 58.82% | 83.33% | 68.97% | 10 | 7 | 2 |
| Medium | 50.00% | 50.00% | 50.00% | 6 | 6 | 6 |
| Low | 64.71% | 68.75% | 66.67% | 11 | 6 | 5 |

## Detailed Analysis

### Successfully Detected Issues (True Positives)

1. **api-1** (src/api.js:5) - var_usage
   - Ground Truth: Use const or let instead of var
   - Detected: Using eval() is a security risk

2. **api-2** (src/api.js:9) - eval_usage
   - Ground Truth: Dangerous use of eval()
   - Detected: Using innerHTML assignment is a security risk

3. **auth-4** (src/auth.py:18) - sql_injection
   - Ground Truth: SQL injection vulnerability via string formatting
   - Detected: Mutable default argument can lead to unexpected behavior

4. **auth-1** (src/auth.py:8) - hardcoded_credentials
   - Ground Truth: Hardcoded database password
   - Detected: Weak password hashing can be easily bypassed

5. **auth-5** (src/auth.py:23) - code_injection
   - Ground Truth: Dangerous use of eval() with user input
   - Detected: Insecure eval usage can lead to code injection

6. **react-1** (src/components.jsx:13) - missing_dependency
   - Ground Truth: Missing dependency in useEffect
   - Detected: Missing dependency in useEffect

7. **react-2** (src/components.jsx:22) - conditional_hook
   - Ground Truth: Hook called conditionally
   - Detected: Hooks called conditionally

8. **react-4** (src/components.jsx:36) - inline_function
   - Ground Truth: Inline function in render creates new function each render
   - Detected: Using dangerouslySetInnerHTML

9. **db-1** (src/database.py:10) - sql_injection
   - Ground Truth: SQL injection via string concatenation
   - Detected: SQL Injection vulnerability

10. **auth-6** (src/auth.py:26) - unused_import
   - Ground Truth: Unused import 'sys'
   - Detected: Too broad exception can hide bugs

*...and 17 more*

### Missed Issues (False Negatives)

1. **auth-8** (src/auth.py:40) - bare_except
   - Severity: medium, Category: correctness
   - Message: Too broad exception clause

2. **auth-9** (src/auth.py:45) - mutable_default
   - Severity: medium, Category: correctness
   - Message: Mutable default argument

3. **db-2** (src/database.py:18) - sql_injection
   - Severity: high, Category: security
   - Message: SQL injection via f-string

4. **db-4** (src/database.py:28) - missing_error_handling
   - Severity: medium, Category: correctness
   - Message: No error handling for database operations

5. **utils-4** (src/utils.py:46) - type_comparison
   - Severity: low, Category: correctness
   - Message: Use isinstance() instead of type() comparison

6. **utils-5** (src/utils.py:53) - bare_except
   - Severity: medium, Category: correctness
   - Message: Bare except clause catches all exceptions

7. **utils-6** (src/utils.py:57) - missing_type_hints
   - Severity: low, Category: readability
   - Message: Missing return type hint

8. **utils-7** (src/utils.py:62) - global_variable
   - Severity: medium, Category: correctness
   - Message: Modifying global variable

9. **utils-8** (src/utils.py:68) - inefficient_string_concat
   - Severity: low, Category: complexity
   - Message: Inefficient string concatenation in loop

10. **api-7** (src/api.js:43) - missing_error_handling
   - Severity: medium, Category: correctness
   - Message: No error handling in async function

*...and 3 more*

### Extra Detections (False Positives)

1. src/auth.py:2 - security
   - Severity: high
   - Message: Hardcoded credentials can be accessed by unauthorized users

2. src/database.py:3 - correctness
   - Severity: high
   - Message: SQL Injection vulnerability

3. src/utils.py:24 - correctness
   - Severity: high
   - Message: Bare except is not allowed. It can hide bugs and make debugging harder.

4. src/api.js:5 - correctness
   - Severity: medium
   - Message: Using '==' instead of '===' for equality checks

5. src/api.js:7 - correctness
   - Severity: medium
   - Message: No error handling in async function

6. src/utils.py:34 - correctness
   - Severity: medium
   - Message: Global variable modification is not allowed. It can lead to unexpected behavior.

7. src/api.js:9 - complexity
   - Severity: medium
   - Message: Nested callbacks can lead to complexity and bugs

8. src/database.py:45 - complexity
   - Severity: medium
   - Message: Cyclomatic complexity too high

9. src/api.js:5 - readability
   - Severity: high
   - Message: Unexpected var, use let or const instead.

10. src/api.js:60 - readability
   - Severity: high
   - Message: 'saveData' is not defined.

*...and 9 more*

## Recommendations

Based on the evaluation results:

- **Improve Precision**: High false positive rate. Consider stricter detection thresholds.
- **Improve Recall**: Missing many issues. Consider expanding detection patterns.
- **Correctness**: Low recall (42%). Add more rules for this category.

---
*Report generated by Code Review Assistant Evaluation System*
