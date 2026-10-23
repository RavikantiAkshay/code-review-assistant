import re
from typing import Dict, List, Optional, Set, Tuple

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

CATEGORY_PRIORITY = {
    "security": 5,
    "correctness": 4,
    "complexity": 3,
    "tests": 2,
    "readability": 1,
}

STATIC_RULE_CATEGORY_MAP = {
    # Special overrides or explicit mappings:
    "E722": "correctness",  # bare except
    "F821": "correctness",  # undefined name
    "F401": "readability",  # unused import
    "E501": "readability",  # line too long
    "CC": "complexity",
    "no-eval": "security",
    "no-implied-eval": "security",
    "react-hooks/rules-of-hooks": "correctness",
    "react-hooks/exhaustive-deps": "correctness",
    "RH-01": "correctness",
    "RH-02": "correctness",
}


def resolve_rule_category(rule_code: Optional[str]) -> Optional[str]:
    """
    Resolve rule category dynamically using standard prefix conventions and patterns
    for Flake8, PyFlakes, Pycodestyle, Bandit, Radon, and ESLint.
    Eliminates the need to manually hardcode hundreds of individual rule codes.
    """
    if not rule_code:
        return None

    code = str(rule_code).strip()
    code_upper = code.upper()
    code_lower = code.lower()

    # 1. Exact match in overrides table
    if code in STATIC_RULE_CATEGORY_MAP:
        return STATIC_RULE_CATEGORY_MAP[code]
    if code_upper in STATIC_RULE_CATEGORY_MAP:
        return STATIC_RULE_CATEGORY_MAP[code_upper]
    if code_lower in STATIC_RULE_CATEGORY_MAP:
        return STATIC_RULE_CATEGORY_MAP[code_lower]

    # Strip tool namespace prefixes (e.g., "PEP8-E722" -> "E722", "FLAKE8-F821" -> "F821")
    clean_code = re.sub(r"^(?:PEP8|FLAKE8|PYFLAKES|ESLINT)[-_]", "", code_upper)

    # 2. Python / Flake8 / Pycodestyle / PyFlakes / Bandit / Radon rules:
    # Bandit security codes: S1xx (hardcoded secrets, exec), S6xx (SQL injection), S7xx, S5xx
    if re.match(r"^S\d{3}$", clean_code):
        return "security"

    # PyFlakes semantic & binding bugs:
    # F8xx (undefined names, unbound locals), F7xx (return/yield outside func), F6xx (duplicate dict keys, is with literal)
    if re.match(r"^F[678]\d{2}$", clean_code):
        return "correctness"

    # Flake8-Bugbear Bxxx (design flaws, mutable defaults B006, common runtime bugs)
    if re.match(r"^B[0-9]\d{2}$", clean_code):
        return "correctness"

    # Pycodestyle syntax & statement errors:
    # E9xx (syntax errors E901, E999) and E7xx (semantic errors: E722 bare except, E711 == None, E721 type comparison)
    if re.match(r"^E(?:9\d{2}|7\d{2})$", clean_code):
        return "correctness"

    # Radon / McCabe cyclomatic complexity: CC, C9xx, C901
    if clean_code == "CC" or re.match(r"^C9\d{2}$", clean_code):
        return "complexity"

    # PyFlakes import & formatting cleanliness: F4xx (unused imports), F5xx (string formatting style)
    if re.match(r"^F[45]\d{2}$", clean_code):
        return "readability"

    # Pycodestyle formatting & style:
    # E1xx (indentation), E2xx (whitespace), E3xx (blank lines), E5xx (line length), Wxxx (warnings)
    if re.match(r"^[EW]\d{3}$", clean_code):
        return "readability"

    # 3. ESLint / JavaScript rules:
    # Security:
    if any(k in code_lower for k in ["security/", "no-eval", "implied-eval", "injection", "csrf", "xss", "crypto", "dangerously"]):
        return "security"

    # React Hooks & React Lifecycle:
    if code_lower.startswith("react-hooks/") or re.match(r"^rh[-_]\d+$", code_lower):
        return "correctness"

    # ESLint Core correctness / runtime bugs:
    if any(code_lower.startswith(p) for p in [
        "no-undef", "no-unreachable", "valid-", "use-isnan", "getter-return",
        "for-direction", "no-dupe-", "no-cond-assign", "no-const-assign",
        "no-loss-of-precision", "no-setter-return", "no-unsafe-"
    ]):
        return "correctness"

    # Complexity:
    if any(code_lower.startswith(p) for p in ["complexity", "max-depth", "max-lines", "max-nested", "max-params", "max-statements"]):
        return "complexity"

    # Testing:
    if any(code_lower.startswith(p) for p in ["jest/", "testing-library/", "mocha/", "cypress/"]):
        return "tests"

    # Formatting / Style:
    if any(code_lower.startswith(p) for p in ["no-unused-", "indent", "semi", "quotes", "space-", "comma-", "brace-style", "no-trailing-"]):
        return "readability"

    return None

CONCEPT_PATTERNS = [
    ("bare_except", [r"\bbare\b.*?\bexcept\b", r"\btoo\s+broad\s+exception\b", r"\be722\b", r"\bcatches?\s+all\s+exceptions?\b"]),
    ("mutable_default", [r"\bmutable\s+default\b", r"\bdefault\s+argument\b"]),
    ("sql_injection", [r"\bsql\s+injection\b", r"\braw\s+query\b", r"\bstring\s+(?:formatting|concatenation)\b.*?\bsql\b"]),
    ("code_injection", [r"\b(?:code\s+injection|dangerous\s+use\s+of\s+eval|insecure\s+eval|eval\s+usage)\b", r"\beval\(", r"\bno-eval\b"]),
    ("hardcoded_credentials", [r"\bhardcoded\b.*?\b(?:password|secret|credential|api[_\s]key|token)\b", r"\bdatabase\s+password\b"]),
    ("weak_hashing", [r"\b(?:md5|sha1)\b", r"\bweak\s+hash", r"\bcryptographically\s+weak\b"]),
    ("unused_import", [r"\bunused\s+import\b", r"\bimported\s+but\s+unused\b", r"\bf401\b"]),
    ("undefined_variable", [r"\bundefined\s+(?:name|variable)\b", r"\bnot\s+defined\b", r"\bf821\b", r"\bno-undef\b"]),
    ("type_comparison", [r"\bisinstance\b", r"\btype\(\)\s+comparison\b", r"\btype\s+comparison\b"]),
    ("global_variable", [r"\bglobal\s+variable\b", r"\bmodifying\s+global\b"]),
    ("missing_docstring", [r"\bmissing\s+docstring\b", r"\bno\s+docstring\b"]),
    ("line_length", [r"\bline\s+too\s+long\b", r"\bmaximum\s+line\s+length\b", r"\be501\b"]),
    ("react_hooks", [r"\bhook\b", r"\buseeffect\b", r"\bconditional\s+hook\b", r"\btop\s+level\b", r"\brh-01\b", r"\brh-02\b"]),
    ("complexity", [r"\bcyclomatic\s+complexity\b", r"\bhigh\s+complexity\b", r"\bcomplexity\b"]),
    ("var_usage", [r"\b(?:unexpected\s+var|use\s+let\s+or\s+const|var\s+usage)\b", r"\bno-var\b"]),
    ("equality", [r"\b(?:==|===|strict\s+equality|equality\s+checks?)\b"]),
    ("error_handling", [r"\b(?:missing|no)\s+error\s+handling\b", r"\bunhandled\s+(?:error|promise|exception)\b"]),
]

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "can",
    "should", "code", "line", "issue", "file", "using", "use",
    "instead", "does", "not", "have", "are", "but", "all", "its",
    "lead", "which", "when", "also", "then", "into"
}


def get_line_range(issue: Dict) -> Tuple[int, int]:
    """
    Extract normalized (start_line, end_line) from issue.
    Returns (start, end) with start <= end.
    """
    s = issue.get("line_start")
    e = issue.get("line_end")
    if s is not None and e is not None:
        try:
            s_int, e_int = int(s), int(e)
            return (min(s_int, e_int), max(s_int, e_int))
        except (ValueError, TypeError):
            pass

    line = issue.get("line") or issue.get("row") or 0
    try:
        line_int = int(line)
        return (line_int, line_int)
    except (ValueError, TypeError):
        return (0, 0)


def are_lines_proximate(r1: Tuple[int, int], r2: Tuple[int, int], tolerance: int = 3) -> bool:
    """Return True if ranges overlap or are within tolerance distance."""
    s1, e1 = r1
    s2, e2 = r2

    if s1 == 0 and e1 == 0:
        return s2 == 0 and e2 == 0
    if s2 == 0 and e2 == 0:
        return False

    # Check overlap
    if max(s1, s2) <= min(e1, e2):
        return True

    # Check distance between disjoint intervals
    gap = max(0, s2 - e1, s1 - e2)
    return gap <= tolerance


def extract_concepts(text: str, code: str = "") -> Set[str]:
    """Extract known semantic concept identifiers from text and code."""
    concepts = set()
    combined = f"{text} {code}".lower()
    for concept_id, patterns in CONCEPT_PATTERNS:
        for pat in patterns:
            if re.search(pat, combined):
                concepts.add(concept_id)
                break
    return concepts


def tokenize_message(text: str) -> Set[str]:
    """Tokenize message into meaningful lower-case words."""
    words = set(re.findall(r"\b[a-z0-9_]{3,}\b", text.lower()))
    return words - STOPWORDS


def _extract_rule_code(issue: Dict) -> str:
    """Extract normalized rule code from issue."""
    rule_obj = issue.get("rule")
    if isinstance(rule_obj, dict):
        return str(rule_obj.get("id") or "").strip().lower()
    if isinstance(rule_obj, str):
        return rule_obj.strip().lower()
    return str(issue.get("code") or "").strip().lower()


def are_issues_duplicate(
    issue1: Dict,
    issue2: Dict,
    line_tolerance: int = 3,
) -> bool:
    """
    Determine whether two issues represent the same defect.
    Evaluates line proximity, semantic concepts, rule codes, and message tokens.
    """
    r1 = get_line_range(issue1)
    r2 = get_line_range(issue2)

    # 1. Must satisfy line proximity
    if not are_lines_proximate(r1, r2, tolerance=line_tolerance):
        return False

    msg1 = issue1.get("message", "")
    msg2 = issue2.get("message", "")
    code1 = _extract_rule_code(issue1)
    code2 = _extract_rule_code(issue2)

    # 2. Explicit rule match
    if code1 and code2 and code1 == code2:
        return True

    # 3. Known semantic concepts match
    c1 = extract_concepts(msg1, code1)
    c2 = extract_concepts(msg2, code2)
    if c1 and c2 and (c1 & c2):
        return True

    tokens1 = tokenize_message(msg1)
    tokens2 = tokenize_message(msg2)

    # 4. Token Jaccard similarity or substantial keyword overlap
    if tokens1 and tokens2:
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard >= 0.30:
            return True
        if len(intersection) >= 2:
            return True

    # 5. Same category and exact line match
    cat1 = issue1.get("category", "").lower()
    cat2 = issue2.get("category", "").lower()
    if r1 == r2 and r1 != (0, 0) and cat1 and cat2 and cat1 == cat2:
        # If both have distinct concept sets that explicitly disagree, do not merge
        if c1 and c2 and not (c1 & c2):
            return False
        # If tokens overlap by at least 1 keyword or neither has conflicting concept
        if not c1 or not c2 or (tokens1 & tokens2):
            return True

    return False


def merge_issue_pair(primary: Dict, secondary: Dict) -> Dict:
    """
    Synthesize two duplicate issues into a single unified record without losing data.
    Preserves rule IDs, code suggestions, snippets, sources, and boosts confidence.
    """
    merged = primary.copy()

    # Merge sources
    def _to_sources(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return []

    s1 = _to_sources(primary.get("sources") or primary.get("source"))
    s2 = _to_sources(secondary.get("sources") or secondary.get("source"))
    combined_sources = list(dict.fromkeys(s1 + s2))
    merged["sources"] = combined_sources
    if "static" in combined_sources and "llm" in combined_sources:
        merged["source"] = "both"
    elif combined_sources:
        merged["source"] = combined_sources[0]
    else:
        merged["source"] = "unknown"

    # Resolve severity (highest severity rank)
    sev1 = primary.get("severity", "low").lower()
    sev2 = secondary.get("severity", "low").lower()
    if SEVERITY_RANK.get(sev2, 0) > SEVERITY_RANK.get(sev1, 0):
        merged["severity"] = sev2
    else:
        merged["severity"] = sev1

    # Resolve category
    cat1 = primary.get("category", "readability").lower()
    cat2 = secondary.get("category", "readability").lower()

    rule_code1 = _extract_rule_code(primary)
    rule_code2 = _extract_rule_code(secondary)
    mapped_cat = resolve_rule_category(rule_code1) or resolve_rule_category(rule_code2)

    if mapped_cat:
        merged["category"] = mapped_cat
    elif CATEGORY_PRIORITY.get(cat2, 0) > CATEGORY_PRIORITY.get(cat1, 0):
        merged["category"] = cat2
    else:
        merged["category"] = cat1

    # Resolve line range
    r1 = get_line_range(primary)
    r2 = get_line_range(secondary)
    if r1 == (0, 0):
        merged["line"] = r2[0]
        merged["line_start"] = r2[0]
        merged["line_end"] = r2[1]
    elif r2 == (0, 0):
        merged["line"] = r1[0]
        merged["line_start"] = r1[0]
        merged["line_end"] = r1[1]
    else:
        merged["line"] = min(r1[0], r2[0]) if r1[0] and r2[0] else (r1[0] or r2[0])
        merged["line_start"] = min(r1[0], r2[0])
        merged["line_end"] = max(r1[1], r2[1])

    # Rule preservation: keep rich rule object
    rule_obj = None
    if isinstance(primary.get("rule"), dict) and primary["rule"].get("id"):
        rule_obj = primary["rule"]
    elif isinstance(secondary.get("rule"), dict) and secondary["rule"].get("id"):
        rule_obj = secondary["rule"]
    elif primary.get("code") or secondary.get("code"):
        code_val = primary.get("code") or secondary.get("code")
        rule_obj = {"id": str(code_val), "link": None}
    merged["rule"] = rule_obj

    # Snippet & Fix preservation
    if not merged.get("snippet") and secondary.get("snippet"):
        merged["snippet"] = secondary["snippet"]
    if not merged.get("fix") and secondary.get("fix"):
        merged["fix"] = secondary["fix"]

    # Message: prefer descriptive human-readable message
    msg1 = primary.get("message", "")
    msg2 = secondary.get("message", "")
    if len(msg2) > len(msg1) and not msg1.startswith("http"):
        merged["message"] = msg2
    else:
        merged["message"] = msg1

    # Confidence: multi-source confirmation yields maximum confidence
    if merged["source"] == "both" or len(combined_sources) > 1:
        merged["confidence"] = 1.0
    else:
        merged["confidence"] = primary.get("confidence") or secondary.get("confidence") or 0.85

    return merged


def deduplicate_reviews(
    *,
    file: str,
    static_reviews: Dict[str, List[Dict]],
    llm_reviews: Dict[str, List[Dict]],
    line_tolerance: int = 3,
) -> Dict[str, List[Dict]]:
    """
    Merge static + LLM reviews with fuzzy line-range overlap and cross-category deduplication.
    Synthesizes rich merged records preserving rules, snippets, fixes, and multi-source tags.
    """
    merged_pool: List[Dict] = []

    def ingest(source_reviews: Dict[str, List[Dict]], source_name: str):
        for category, issues in source_reviews.items():
            for issue in issues:
                item = issue.copy()
                item["source"] = source_name
                item["sources"] = [source_name]

                # Dynamically resolve category if rule code specifies higher priority category
                rule_code = _extract_rule_code(item)
                rule_cat = resolve_rule_category(rule_code)

                if rule_cat and (item.get("category") in [None, "", "readability", "lint", "syntax"] or CATEGORY_PRIORITY.get(rule_cat, 0) > CATEGORY_PRIORITY.get(item.get("category", ""), 0)):
                    item["category"] = rule_cat
                elif "category" not in item:
                    item["category"] = category

                if "file" not in item:
                    item["file"] = file

                # Check if item matches any existing item in merged_pool
                matched_idx = -1
                for idx, existing in enumerate(merged_pool):
                    if are_issues_duplicate(existing, item, line_tolerance=line_tolerance):
                        matched_idx = idx
                        break

                if matched_idx >= 0:
                    merged_pool[matched_idx] = merge_issue_pair(merged_pool[matched_idx], item)
                else:
                    merged_pool.append(item)

    # Ingest static analysis first, then LLM reviews
    ingest(static_reviews, "static")
    ingest(llm_reviews, "llm")

    # Group back by category
    final: Dict[str, List[Dict]] = {
        "correctness": [],
        "security": [],
        "complexity": [],
        "readability": [],
        "tests": [],
    }

    for issue in merged_pool:
        cat = issue.get("category", "readability").lower()
        if cat not in final:
            final[cat] = []
        final[cat].append(issue)

    return final
