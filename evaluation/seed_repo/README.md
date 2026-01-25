# Seed Repository for Code Review Assistant Evaluation

This repository contains intentionally buggy code files for evaluating the Code Review Assistant.

## Issue Categories

- **Security**: SQL injection, XSS, hardcoded credentials
- **Correctness**: Logic errors, type errors, null handling
- **Complexity**: Deeply nested code, long functions
- **Readability**: Poor naming, missing docstrings, PEP8 violations
- **Tests**: Missing test coverage hints

## Files

- `src/auth.py` - Authentication with security issues
- `src/database.py` - Database operations with SQL injection
- `src/utils.py` - Utility functions with complexity issues
- `src/api.js` - JavaScript API with various issues
- `src/components.jsx` - React component with hooks issues
