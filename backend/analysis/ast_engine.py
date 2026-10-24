import ast
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SymbolNode:
    name: str
    kind: str  # "function", "method", "class"
    file_path: str
    line_start: int
    line_end: int
    signature: str
    docstring: Optional[str] = None
    complexity: int = 1
    calls: List[str] = field(default_factory=list)
    line_count: int = 1


@dataclass
class ImportEdge:
    source_file: str
    module: str
    names: List[str]
    line: int


class SymbolGraph:
    """
    In-memory directed dependency graph of symbols, function calls, and module imports.
    Provides blast-radius traversal without requiring an external database.
    """

    def __init__(self):
        self.symbols: Dict[str, SymbolNode] = {}  # key: f"{file_path}::{symbol_name}"
        self.call_edges: Dict[str, Set[str]] = {}  # caller_key -> set of callee_keys
        self.reverse_call_edges: Dict[str, Set[str]] = {}  # callee_key -> set of caller_keys
        self.import_edges: List[ImportEdge] = []

    def add_symbol(self, symbol: SymbolNode):
        key = f"{symbol.file_path}::{symbol.name}"
        self.symbols[key] = symbol
        self.call_edges.setdefault(key, set())
        self.reverse_call_edges.setdefault(key, set())

    def add_call(self, caller_key: str, callee_name: str, callee_file: Optional[str] = None):
        if callee_file:
            callee_key = f"{callee_file}::{callee_name}"
        else:
            # If callee file is unknown, search known symbols matching callee_name
            matching = [k for k in self.symbols if k.endswith(f"::{callee_name}")]
            callee_key = matching[0] if matching else f"external::{callee_name}"

        self.call_edges.setdefault(caller_key, set()).add(callee_key)
        self.reverse_call_edges.setdefault(callee_key, set()).add(caller_key)

    def find_blast_radius(
        self,
        symbol_name: str,
        file_path: Optional[str] = None,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Compute upstream blast radius: find all callers that depend on this symbol
        up to `max_depth` call hops.
        """
        target_keys = []
        if file_path:
            specific_key = f"{file_path}::{symbol_name}"
            if specific_key in self.symbols or specific_key in self.reverse_call_edges:
                target_keys.append(specific_key)

        if not target_keys:
            target_keys = [k for k in self.symbols if k.endswith(f"::{symbol_name}")]

        if not target_keys:
            return []

        visited = set()
        results = []

        queue: List[Tuple[str, int]] = [(k, 0) for k in target_keys]

        while queue:
            current_key, depth = queue.pop(0)
            if current_key in visited or depth > max_depth:
                continue
            visited.add(current_key)

            if depth > 0:
                sym = self.symbols.get(current_key)
                file_part, sym_part = current_key.split("::", 1) if "::" in current_key else ("unknown", current_key)
                results.append({
                    "symbol": sym_part,
                    "file_path": sym.file_path if sym else file_part,
                    "signature": sym.signature if sym else "",
                    "line_start": sym.line_start if sym else 0,
                    "depth": depth,
                })

            upstream_callers = self.reverse_call_edges.get(current_key, set())
            for caller in upstream_callers:
                if caller not in visited and depth < max_depth:
                    queue.append((caller, depth + 1))

        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_symbols": len(self.symbols),
            "total_call_edges": sum(len(v) for v in self.call_edges.values()),
            "symbols": {k: asdict(v) for k, v in self.symbols.items()},
        }


# ==============================================================================
# Python AST Visitor & Anti-Pattern Rule Engine
# ==============================================================================

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, code_lines: List[str]):
        self.file_path = file_path
        self.code_lines = code_lines
        self.symbols: List[SymbolNode] = []
        self.imports: List[ImportEdge] = []
        self.issues: List[Dict[str, Any]] = []

        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.current_function_calls: List[str] = []
        self.global_vars_declared: Set[str] = set()

        # Track loaded vs imported names for unused import detection
        self.imported_names: Dict[str, int] = {}  # name -> line
        self.loaded_names: Set[str] = set()

    def _get_line_snippet(self, lineno: int, end_lineno: Optional[int] = None) -> str:
        if not self.code_lines or lineno < 1:
            return ""
        start = max(0, lineno - 1)
        end = end_lineno if (end_lineno and end_lineno >= lineno) else lineno
        end = min(len(self.code_lines), end)
        return "\n".join(self.code_lines[start:end]).strip()

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity by counting decision/branching points."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (
                ast.If, ast.While, ast.For, ast.AsyncFor,
                ast.ExceptHandler, ast.With, ast.AsyncWith,
                ast.Assert, ast.IfExp
            )):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # Each 'and' or 'or' adds a branch
                complexity += len(child.values) - 1
        return complexity

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_names[name] = node.lineno
            self.imports.append(ImportEdge(
                source_file=self.file_path,
                module=alias.name,
                names=[name],
                line=node.lineno,
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        names = []
        for alias in node.names:
            name = alias.asname or alias.name
            names.append(name)
            self.imported_names[name] = node.lineno

        self.imports.append(ImportEdge(
            source_file=self.file_path,
            module=module,
            names=names,
            line=node.lineno,
        ))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.loaded_names.add(node.id)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        self.current_class = node.name

        docstring = ast.get_docstring(node)
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        self.symbols.append(SymbolNode(
            name=node.name,
            kind="class",
            file_path=self.file_path,
            line_start=start_line,
            line_end=end_line,
            signature=f"class {node.name}",
            docstring=docstring,
            line_count=max(1, end_line - start_line + 1),
        ))


        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: Any, is_async: bool):
        prev_func = self.current_function
        prev_calls = self.current_function_calls
        self.current_function = node.name
        self.current_function_calls = []
        self.global_vars_declared = set()

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        complexity = self._calculate_complexity(node)
        docstring = ast.get_docstring(node)

        # Build signature string
        args_str = ", ".join(arg.arg for arg in node.args.args)
        prefix = "async def " if is_async else "def "
        sig = f"{prefix}{node.name}({args_str})"
        kind = "method" if self.current_class else "function"

        # Check high cyclomatic complexity
        if complexity > 10:
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "medium",
                "category": "complexity",
                "type": "high_cyclomatic_complexity",
                "code": "AST-COMPLEXITY",
                "message": f"High cyclomatic complexity ({complexity}) in {node.name}",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "Refactor function by breaking nested logic into smaller helper functions",
                "source": "ast",
            })

        # Check function too long
        line_count = end_line - start_line + 1
        if line_count > 40:
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "medium",
                "category": "complexity",
                "type": "function_too_long",
                "code": "AST-LONG-FUNC",
                "message": f"Function '{node.name}' is too long ({line_count} lines)",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "Extract sub-tasks into dedicated modular functions",
                "source": "ast",
            })

        # Rule 1: Mutable default argument
        all_defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
        for default_expr in all_defaults:
            if isinstance(default_expr, (ast.List, ast.Dict, ast.Set)) or (
                isinstance(default_expr, ast.Call) and getattr(default_expr.func, "id", None) in ["list", "dict", "set"]
            ):
                self.issues.append({
                    "file": self.file_path,
                    "line": default_expr.lineno,
                    "severity": "medium",
                    "category": "correctness",
                    "type": "mutable_default",
                    "code": "AST-MUTABLE-DEFAULT",
                    "message": "Mutable default argument in function definition",
                    "snippet": self._get_line_snippet(default_expr.lineno),
                    "fix": "Use None as the default value and initialize the mutable object inside the function body",
                    "source": "ast",
                })


        # Rule 4: Poor naming (single letter variable names)
        if len(node.args.args) >= 3 and all(len(a.arg) == 1 for a in node.args.args):
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "low",
                "category": "readability",
                "type": "poor_naming",
                "code": "AST-POOR-NAMING",
                "message": "Single letter variable names in function signature",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "Use descriptive parameter names instead of single-letter variables",
                "source": "ast",
            })

        self.generic_visit(node)

        self.symbols.append(SymbolNode(
            name=node.name,
            kind=kind,
            file_path=self.file_path,
            line_start=start_line,
            line_end=end_line,
            signature=sig,
            docstring=docstring,
            complexity=complexity,
            calls=list(set(self.current_function_calls)),
            line_count=line_count,
        ))

        self.current_function = prev_func
        self.current_function_calls = prev_calls

    def visit_Global(self, node: ast.Global):
        self.global_vars_declared.update(node.names)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check global variable modification
        if self.current_function and self.global_vars_declared:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in self.global_vars_declared:
                    self.issues.append({
                        "file": self.file_path,
                        "line": node.lineno,
                        "severity": "medium",
                        "category": "correctness",
                        "type": "global_variable",
                        "code": "AST-GLOBAL-VAR",
                        "message": f"Modifying global variable '{target.id}'",
                        "snippet": self._get_line_snippet(node.lineno),
                        "fix": f"Refactor to pass '{target.id}' as a parameter or encapsulate in a stateful class",
                        "source": "ast",
                    })

        # Check hardcoded credentials in literal assignments
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_upper = target.id.upper()
                if any(k in name_upper for k in ["PASSWORD", "SECRET_KEY", "API_KEY", "API_SECRET", "ACCESS_TOKEN"]):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        val_str = node.value.value
                        if len(val_str) >= 4 and not val_str.startswith(("os.", "env", "placeholder")):
                            self.issues.append({
                                "file": self.file_path,
                                "line": node.lineno,
                                "severity": "high",
                                "category": "security",
                                "type": "hardcoded_credentials",
                                "code": "AST-HARDCODED-SECRET",
                                "message": f"Hardcoded credential detected in variable '{target.id}'",
                                "snippet": self._get_line_snippet(node.lineno),
                                "fix": f"{target.id} = os.getenv('{target.id}')",
                                "source": "ast",
                            })

        # Check SQL injection via string concatenation or f-string
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.lower() in ["query", "sql", "statement", "stmt"]:
                if isinstance(node.value, ast.JoinedStr) or (
                    isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add)
                ):
                    code_snippet = self._get_line_snippet(node.lineno)
                    if any(sql_word in code_snippet.upper() for sql_word in ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE"]):
                        self.issues.append({
                            "file": self.file_path,
                            "line": node.lineno,
                            "severity": "high",
                            "category": "security",
                            "type": "sql_injection",
                            "code": "AST-SQL-INJECTION",
                            "message": "SQL injection vulnerability via string concatenation / formatting",
                            "snippet": code_snippet,
                            "fix": "Use parameterized queries with database query placeholders (%s or ?)",
                            "source": "ast",
                        })

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        # Check global variable augmented assignment (e.g. counter += 1)
        if self.current_function and isinstance(node.target, ast.Name):
            if node.target.id in self.global_vars_declared:
                self.issues.append({
                    "file": self.file_path,
                    "line": node.lineno,
                    "severity": "medium",
                    "category": "correctness",
                    "type": "global_variable",
                    "code": "AST-GLOBAL-VAR",
                    "message": f"Modifying global variable '{node.target.id}'",
                    "snippet": self._get_line_snippet(node.lineno),
                    "fix": "Avoid modifying global variables; return new state instead",
                    "source": "ast",
                })
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Bare except: 'except:' with no exception class specified
        if node.type is None:
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "medium",
                "category": "correctness",
                "type": "bare_except",
                "code": "AST-BARE-EXCEPT",
                "message": "Too broad exception clause catches all exceptions (including SystemExit)",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "except Exception as e:",
                "source": "ast",
            })
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        # Rule: Use isinstance() instead of type() comparison
        # e.g., if type(x) == str: or if type(x) is str:
        if isinstance(node.left, ast.Call) and getattr(node.left.func, "id", None) == "type":
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "low",
                "category": "correctness",
                "type": "type_comparison",
                "code": "AST-TYPE-COMPARE",
                "message": "Use isinstance() instead of type() comparison",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "isinstance(target, expected_type)",
                "source": "ast",
            })

        # Rule: Comparison to None: if val == None:
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if (isinstance(comparator, ast.Constant) and comparator.value is None) or (
                    isinstance(node.left, ast.Constant) and node.left.value is None
                ):
                    self.issues.append({
                        "file": self.file_path,
                        "line": node.lineno,
                        "severity": "low",
                        "category": "readability",
                        "type": "comparison_to_none",
                        "code": "AST-IS-NONE",
                        "message": "Use 'is None' instead of '== None'",
                        "snippet": self._get_line_snippet(node.lineno),
                        "fix": "is None" if isinstance(op, ast.Eq) else "is not None",
                        "source": "ast",
                    })

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Track function calls for call graph
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and self.current_function:
            self.current_function_calls.append(func_name)

        # Rule: Insecure eval() / exec()
        if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec"]:
            self.issues.append({
                "file": self.file_path,
                "line": node.lineno,
                "severity": "high",
                "category": "security",
                "type": "code_injection",
                "code": "AST-EVAL-USAGE",
                "message": f"Dangerous use of {node.func.id}() with user input",
                "snippet": self._get_line_snippet(node.lineno),
                "fix": "Avoid dynamic code execution; use safe parsing (e.g. ast.literal_eval, json.loads)",
                "source": "ast",
            })

        # Rule: Weak password hashing (md5, sha1)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in ["md5", "sha1"]:
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                    self.issues.append({
                        "file": self.file_path,
                        "line": node.lineno,
                        "severity": "high",
                        "category": "security",
                        "type": "weak_hashing",
                        "code": "AST-WEAK-HASH",
                        "message": f"{node.func.attr.upper()} is cryptographically weak for password hashing",
                        "snippet": self._get_line_snippet(node.lineno),
                        "fix": "Use a secure slow-hashing algorithm such as bcrypt, argon2, or hashlib.pbkdf2_hmac",
                        "source": "ast",
                    })

        # Rule: SQL injection in database execute calls (e.g. cursor.execute(f"..."))
        if isinstance(node.func, ast.Attribute) and node.func.attr in ["execute", "executescript", "raw", "query"]:
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, (ast.JoinedStr, ast.BinOp)):
                    code_snippet = self._get_line_snippet(node.lineno)
                    self.issues.append({
                        "file": self.file_path,
                        "line": node.lineno,
                        "severity": "high",
                        "category": "security",
                        "type": "sql_injection",
                        "code": "AST-SQL-INJECTION",
                        "message": "SQL injection vulnerability via dynamic string in execute query",
                        "snippet": code_snippet,
                        "fix": "cursor.execute('SELECT ... WHERE id = %s', (val,))",
                        "source": "ast",
                    })

        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self._check_loop_string_concat(node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self._check_loop_string_concat(node)
        self.generic_visit(node)

    def _check_loop_string_concat(self, loop_node: Any):
        """Check for inefficient string concatenation in loop."""
        for child in ast.walk(loop_node):
            if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                snippet = self._get_line_snippet(child.lineno)
                if any(x in snippet for x in ['"', "'", "str(", "\\n"]):
                    self.issues.append({
                        "file": self.file_path,
                        "line": child.lineno,
                        "severity": "low",
                        "category": "complexity",
                        "type": "inefficient_string_concat",
                        "code": "AST-STRING-CONCAT",
                        "message": "Inefficient string concatenation in loop",
                        "snippet": snippet,
                        "fix": "Collect chunks in a list and join them using ''.join(chunks)",
                        "source": "ast",
                    })
                    break
            elif isinstance(child, ast.Assign) and isinstance(child.value, ast.BinOp) and isinstance(child.value.op, ast.Add):
                snippet = self._get_line_snippet(child.lineno)
                if any(x in snippet for x in ['"', "'", "str(", "\\n"]):
                    self.issues.append({
                        "file": self.file_path,
                        "line": child.lineno,
                        "severity": "low",
                        "category": "complexity",
                        "type": "inefficient_string_concat",
                        "code": "AST-STRING-CONCAT",
                        "message": "Inefficient string concatenation in loop",
                        "snippet": snippet,
                        "fix": "Collect chunks in a list and join them using ''.join(chunks)",
                        "source": "ast",
                    })
                    break

    def finalize(self):
        """Perform cross-checks like unused imports."""
        for name, lineno in self.imported_names.items():
            if name not in self.loaded_names and not name.startswith("_"):
                self.issues.append({
                    "file": self.file_path,
                    "line": lineno,
                    "severity": "low",
                    "category": "readability",
                    "type": "unused_import",
                    "code": "AST-UNUSED-IMPORT",
                    "message": f"Unused import '{name}'",
                    "snippet": self._get_line_snippet(lineno),
                    "fix": f"# Remove unused import '{name}'",
                    "source": "ast",
                })


# ==============================================================================
# JavaScript / JSX Scanner & Anti-Pattern Rule Engine
# ==============================================================================

class JavaScriptASTAnalyzer:
    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.splitlines()
        self.symbols: List[SymbolNode] = []
        self.imports: List[ImportEdge] = []
        self.issues: List[Dict[str, Any]] = []

    def _get_snippet(self, lineno: int) -> str:
        idx = lineno - 1
        if 0 <= idx < len(self.lines):
            return self.lines[idx].strip()
        return ""

    def analyze(self) -> Tuple[List[SymbolNode], List[ImportEdge], List[Dict[str, Any]]]:
        # Extract function declarations & arrow functions
        func_patterns = [
            (r"(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)", "function"),
            (r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>", "function"),
            (r"class\s+([a-zA-Z0-9_$]+)", "class"),
        ]

        for line_num, line in enumerate(self.lines, start=1):
            for pat, kind in func_patterns:
                m = re.search(pat, line)
                if m:
                    name = m.group(1)
                    sig = m.group(0)
                    self.symbols.append(SymbolNode(
                        name=name,
                        kind=kind,
                        file_path=self.file_path,
                        line_start=line_num,
                        line_end=line_num,
                        signature=sig,
                    ))

            # Imports extraction
            import_m = re.search(r"import\s+(?:\{([^}]+)\}|\*\s+as\s+([a-zA-Z0-9_$]+)|([a-zA-Z0-9_$]+))\s+from\s+['\"]([^'\"]+)['\"]", line)
            if import_m:
                names = [n.strip() for n in (import_m.group(1) or import_m.group(2) or import_m.group(3) or "").split(",") if n.strip()]
                module = import_m.group(4)
                self.imports.append(ImportEdge(
                    source_file=self.file_path,
                    module=module,
                    names=names,
                    line=line_num,
                ))

            # Rule: var usage
            if re.search(r"^\s*var\s+[a-zA-Z0-9_$]+", line):
                self.issues.append({
                    "file": self.file_path,
                    "line": line_num,
                    "severity": "low",
                    "category": "readability",
                    "type": "var_usage",
                    "code": "AST-JS-VAR",
                    "message": "Use const or let instead of var",
                    "snippet": self._get_snippet(line_num),
                    "fix": line.replace("var ", "const "),
                    "source": "ast",
                })

            # Rule: Dangerous eval usage
            if re.search(r"\beval\s*\(", line):
                self.issues.append({
                    "file": self.file_path,
                    "line": line_num,
                    "severity": "high",
                    "category": "security",
                    "type": "eval_usage",
                    "code": "AST-JS-EVAL",
                    "message": "Dangerous use of eval()",
                    "snippet": self._get_snippet(line_num),
                    "fix": "Avoid dynamic code execution with eval()",
                    "source": "ast",
                })

            # Rule: innerHTML / dangerouslySetInnerHTML
            if re.search(r"\.innerHTML\s*=|dangerouslySetInnerHTML", line):
                self.issues.append({
                    "file": self.file_path,
                    "line": line_num,
                    "severity": "high",
                    "category": "security",
                    "type": "xss_vulnerability",
                    "code": "AST-JS-XSS",
                    "message": "innerHTML can lead to XSS vulnerabilities",
                    "snippet": self._get_snippet(line_num),
                    "fix": "Use textContent or sanitized React elements instead of innerHTML",
                    "source": "ast",
                })

            # Rule: Loose equality (== instead of ===)
            if re.search(r"[^=!]==[^=]", line):
                self.issues.append({
                    "file": self.file_path,
                    "line": line_num,
                    "severity": "medium",
                    "category": "correctness",
                    "type": "loose_equality",
                    "code": "AST-JS-EQUALITY",
                    "message": "Use === instead of ==",
                    "snippet": self._get_snippet(line_num),
                    "fix": line.replace("==", "==="),
                    "source": "ast",
                })

            # Rule: Missing semicolon
            code_only = re.sub(r"//.*$", "", line).strip()
            if code_only and not code_only.endswith((";", "{", "}", ",", "(", ")", ":", "[", "]", "/*", "*/")) and not code_only.startswith(("//", "/*", "*", "import", "export")):
                if any(code_only.startswith(k) for k in ["const ", "let ", "return ", "var "]):
                    self.issues.append({
                        "file": self.file_path,
                        "line": line_num,
                        "severity": "low",
                        "category": "readability",
                        "type": "missing_semicolon",
                        "code": "AST-JS-SEMI",
                        "message": "Missing semicolon",
                        "snippet": self._get_snippet(line_num),
                        "fix": f"{code_only};",
                        "source": "ast",
                    })

            # Rule: console.log in production
            if re.search(r"console\.log\s*\(", line):
                self.issues.append({
                    "file": self.file_path,
                    "line": line_num,
                    "severity": "low",
                    "category": "readability",
                    "type": "console_log",
                    "code": "AST-JS-CONSOLE",
                    "message": "console.log left in production code",
                    "snippet": self._get_snippet(line_num),
                    "fix": "// Remove console.log before production release",
                    "source": "ast",
                })

            # Rule: Conditional Hook
            if re.search(r"use(?:State|Effect|Ref|Context|Memo|Callback)\s*\(", line):
                # Check preceding lines inside an 'if' block
                context_prev = " ".join(self.lines[max(0, line_num - 5):line_num - 1])
                if "if (" in context_prev or "if(" in context_prev:
                    self.issues.append({
                        "file": self.file_path,
                        "line": line_num,
                        "severity": "high",
                        "category": "correctness",
                        "type": "conditional_hook",
                        "code": "AST-JS-HOOK",
                        "message": "Hook called conditionally",
                        "snippet": self._get_snippet(line_num),
                        "fix": "Move React hook calls to the component top level",
                        "source": "ast",
                    })

            # Rule: Missing error handling in async function
            if re.search(r"async\s+function|async\s*\(.*?\)\s*=>", line):
                # Look forward up to 15 lines to verify if try/catch exists
                window = "\n".join(self.lines[line_num - 1:min(len(self.lines), line_num + 15)])
                if "try {" not in window and "try{" not in window:
                    self.issues.append({
                        "file": self.file_path,
                        "line": line_num,
                        "severity": "medium",
                        "category": "correctness",
                        "type": "missing_error_handling",
                        "code": "AST-JS-ERROR-HANDLING",
                        "message": "No error handling in async function",
                        "snippet": self._get_snippet(line_num),
                        "fix": "Wrap asynchronous operations inside a try...catch block",
                        "source": "ast",
                    })

        return self.symbols, self.imports, self.issues


# ==============================================================================
# Public API Endpoints for Code Review Engine & MCP Tools
# ==============================================================================

def analyze_code_ast(file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
    """
    Run AST rule engine on code and return detected anti-patterns and bugs.
    Deterministic, zero-token, zero-latency verification.
    """
    lang = language.lower() if language else ""

    if lang in ["python", "py"]:
        try:
            tree = ast.parse(content, filename=file_path)
            lines = content.splitlines()
            visitor = PythonASTVisitor(file_path=file_path, code_lines=lines)
            visitor.visit(tree)
            visitor.finalize()
            return visitor.issues
        except SyntaxError as e:
            return [{
                "file": file_path,
                "line": e.lineno or 1,
                "severity": "high",
                "category": "correctness",
                "type": "syntax_error",
                "code": "AST-SYNTAX-ERROR",
                "message": f"SyntaxError: {e.msg}",
                "snippet": e.text.strip() if e.text else "",
                "fix": "Fix invalid syntax",
                "source": "ast",
            }]
        except Exception:
            return []

    elif lang in ["javascript", "js", "jsx", "typescript", "ts", "tsx"]:
        try:
            analyzer = JavaScriptASTAnalyzer(file_path=file_path, content=content)
            _, _, issues = analyzer.analyze()
            return issues
        except Exception:
            return []

    return []


def extract_ast_symbols(file_path: str, content: str, language: str) -> Dict[str, Any]:
    """
    Extract symbols (functions, classes, methods), complexity, and imports.
    """
    lang = language.lower() if language else ""
    symbols: List[SymbolNode] = []
    imports: List[ImportEdge] = []

    if lang in ["python", "py"]:
        try:
            tree = ast.parse(content, filename=file_path)
            lines = content.splitlines()
            visitor = PythonASTVisitor(file_path=file_path, code_lines=lines)
            visitor.visit(tree)
            symbols = visitor.symbols
            imports = visitor.imports
        except Exception:
            pass
    elif lang in ["javascript", "js", "jsx", "typescript", "ts", "tsx"]:
        try:
            analyzer = JavaScriptASTAnalyzer(file_path=file_path, content=content)
            symbols, imports, _ = analyzer.analyze()
        except Exception:
            pass

    return {
        "file": file_path,
        "symbols": [asdict(s) for s in symbols],
        "imports": [{"module": i.module, "names": i.names, "line": i.line} for i in imports],
        "metrics": {
            "symbol_count": len(symbols),
            "function_count": len([s for s in symbols if s.kind in ["function", "method"]]),
            "class_count": len([s for s in symbols if s.kind == "class"]),
            "average_complexity": round(sum(s.complexity for s in symbols) / max(1, len(symbols)), 2),
        }
    }


def build_repository_symbol_graph(file_paths: List[str], base_dir: str) -> SymbolGraph:
    """
    Construct a connected repository-wide symbol graph from a list of files.
    Enables cross-file dependency analysis and blast-radius queries.
    """
    graph = SymbolGraph()

    for rel_path in file_paths:
        abs_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(abs_path):
            continue

        ext = os.path.splitext(rel_path)[1].lower()
        lang = "python" if ext in [".py"] else ("javascript" if ext in [".js", ".jsx", ".ts", ".tsx"] else "")
        if not lang:
            continue

        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            data = extract_ast_symbols(rel_path, content, lang)
            for sym_data in data["symbols"]:
                node = SymbolNode(**sym_data)
                graph.add_symbol(node)
                for callee in node.calls:
                    graph.add_call(f"{rel_path}::{node.name}", callee)
        except Exception:
            continue

    return graph


def get_language_for_file(file_path: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".py":
        return "python"
    elif ext in [".js", ".jsx"]:
        return "javascript" if ext == ".js" else "jsx"
    return None
