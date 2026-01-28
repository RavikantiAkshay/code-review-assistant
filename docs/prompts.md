# Prompt Templates Documentation

This document describes the prompts used by the Code Review Assistant's LLM component.

## Overview

The LLM review uses Groq's `llama-3.1-8b-instant` model with structured JSON output for consistent, parseable results.

## Main Code Review Prompt

### Location
`backend/llm/prompts/code_review.txt`

### Template

```
You are a senior code reviewer. Analyze the following {language} code and identify issues.

**File:** {file_path}
**Language:** {language}

```{language}
{code}
```

Review the code for:
1. **Correctness** - Logic errors, type issues, null handling
2. **Security** - Vulnerabilities, injections, data exposure
3. **Complexity** - Cyclomatic complexity, nesting depth
4. **Readability** - Naming, documentation, formatting
5. **Tests** - Missing test coverage indicators

For each issue found, provide:
- `line`: Line number where the issue occurs
- `severity`: "high", "medium", or "low"
- `message`: Clear description of the issue
- `category`: One of "correctness", "security", "complexity", "readability", "tests"
- `snippet`: The problematic code snippet
- `fix`: Suggested corrected code

Return your response as valid JSON matching this schema:
{json_schema}
```

### Variables

| Variable | Description |
|----------|-------------|
| `{language}` | Programming language (python, javascript, etc.) |
| `{file_path}` | Path to the file being reviewed |
| `{code}` | The actual source code content |
| `{json_schema}` | Expected JSON output structure |

## JSON Output Schema

```json
{
  "issues": [
    {
      "line": 10,
      "severity": "high",
      "message": "SQL injection vulnerability via string formatting",
      "category": "security",
      "snippet": "query = f\"SELECT * FROM users WHERE id = {user_id}\"",
      "fix": "query = \"SELECT * FROM users WHERE id = ?\"; cursor.execute(query, (user_id,))"
    }
  ]
}
```

## Ruleset-Specific Prompts

When a ruleset is selected, additional context is added to the prompt:

### PEP8 Ruleset
```
Focus particularly on:
- PEP 8 style compliance
- Naming conventions (snake_case for functions/variables)
- Import organization
- Line length limits
- Whitespace usage
```

### OWASP Top 10 Ruleset
```
Focus particularly on:
- Injection vulnerabilities (SQL, command, LDAP)
- Broken authentication patterns
- Sensitive data exposure
- Security misconfiguration
- Cross-site scripting (XSS)
```

### React Hooks Ruleset
```
Focus particularly on:
- Rules of Hooks violations
- Missing dependencies in useEffect
- Conditional hook calls
- Proper cleanup in effects
- State management patterns
```

## LLM Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| Model | `llama-3.1-8b-instant` | Groq's fast inference model |
| Temperature | `0` | Deterministic output |
| Timeout | `30s` | Request timeout |
| Max Retries | `3` | Retry on transient errors |

## Error Handling

The LLM reviewer handles:
- **Rate limiting**: Exponential backoff with retry
- **Timeout errors**: Automatic retry up to 3 times
- **Invalid JSON**: Regex extraction of JSON from response
- **Missing fields**: Default values for optional fields

## Customization

### Adding Custom Rulesets

1. Edit `backend/rulesets/registry.py`:
```python
RULESETS["my_ruleset"] = {
    "name": "My Custom Ruleset",
    "description": "Custom rules for my project",
    "language": "python",
    "categories": ["correctness", "security"],
    "rules": [
        {"id": "MY001", "name": "Custom Rule", "link": "..."}
    ]
}
```

2. The ruleset context is automatically included in the prompt.

### Modifying the Base Prompt

Edit `backend/llm/prompts/code_review.txt` to change:
- Review focus areas
- Output format requirements
- Additional context or constraints
