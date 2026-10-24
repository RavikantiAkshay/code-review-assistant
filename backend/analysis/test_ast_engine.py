import pytest
from backend.analysis.ast_engine import (
    analyze_code_ast,
    extract_ast_symbols,
    SymbolGraph,
    SymbolNode,
)


def test_python_ast_anti_patterns():
    code = """
import sys
import hashlib

DATABASE_PASSWORD = "super_secret_admin_pw"
counter = 0

def bad_function(items=[]):
    global counter
    counter += 1
    if type(items) == list:
        pass
    if counter == None:
        pass
    try:
        val = eval("1 + 1")
        h = hashlib.md5(b"password").hexdigest()
        query = f"SELECT * FROM users WHERE name = '{val}'"
    except:
        pass
    return True
"""
    issues = analyze_code_ast("src/auth.py", code, "python")
    types = {i["type"] for i in issues}

    assert "bare_except" in types
    assert "mutable_default" in types
    assert "type_comparison" in types
    assert "comparison_to_none" in types
    assert "global_variable" in types
    assert "code_injection" in types
    assert "weak_hashing" in types
    assert "sql_injection" in types
    assert "hardcoded_credentials" in types
    assert "unused_import" in types

    # Check categories
    for issue in issues:
        if issue["type"] in ["bare_except", "mutable_default", "type_comparison", "global_variable"]:
            assert issue["category"] == "correctness"
        elif issue["type"] in ["code_injection", "weak_hashing", "sql_injection", "hardcoded_credentials"]:
            assert issue["category"] == "security"
        elif issue["type"] in ["comparison_to_none", "unused_import"]:
            assert issue["category"] == "readability"


def test_javascript_ast_anti_patterns():
    code = """
import React, { useState } from 'react';

var apiUrl = "https://api.example.com";

function testComponent(props) {
    if (props.condition) {
        const [state, setState] = useState(0);
    }
    if (x == null) {
        eval("alert(1)");
        document.getElementById("box").innerHTML = "<b>hello</b>";
    }
}

async function fetchUserData(userId) {
    const res = await fetch(apiUrl);
    return res.json();
}
"""
    issues = analyze_code_ast("src/Component.jsx", code, "javascript")
    types = {i["type"] for i in issues}

    assert "var_usage" in types
    assert "conditional_hook" in types
    assert "eval_usage" in types
    assert "xss_vulnerability" in types
    assert "loose_equality" in types
    assert "missing_error_handling" in types


def test_symbol_extraction_and_complexity():
    code = """
class Calculator:
    def add(self, a, b):
        return a + b

def complex_function(x, y):
    if x > 0:
        if y > 0:
            for i in range(10):
                if i % 2 == 0:
                    pass
    return x + y
"""
    result = extract_ast_symbols("src/math.py", code, "python")
    symbols = result["symbols"]
    sym_map = {s["name"]: s for s in symbols}

    assert "Calculator" in sym_map
    assert "add" in sym_map
    assert "complex_function" in sym_map
    assert sym_map["complex_function"]["complexity"] > 1
    assert result["metrics"]["function_count"] == 2
    assert result["metrics"]["class_count"] == 1


def test_symbol_graph_blast_radius():
    graph = SymbolGraph()

    # Model: Controller calls Service calls Repository
    repo_node = SymbolNode(
        name="find_user",
        kind="method",
        file_path="src/repository.py",
        line_start=10,
        line_end=15,
        signature="def find_user(user_id):",
    )
    service_node = SymbolNode(
        name="get_user_profile",
        kind="function",
        file_path="src/service.py",
        line_start=20,
        line_end=30,
        signature="def get_user_profile(user_id):",
        calls=["find_user"],
    )
    controller_node = SymbolNode(
        name="handle_request",
        kind="function",
        file_path="src/controller.py",
        line_start=5,
        line_end=15,
        signature="def handle_request(req):",
        calls=["get_user_profile"],
    )

    graph.add_symbol(repo_node)
    graph.add_symbol(service_node)
    graph.add_symbol(controller_node)

    graph.add_call("src/service.py::get_user_profile", "find_user", "src/repository.py")
    graph.add_call("src/controller.py::handle_request", "get_user_profile", "src/service.py")

    # Blast radius of modifying find_user
    blast = graph.find_blast_radius("find_user", "src/repository.py", max_depth=3)

    assert len(blast) == 2
    depth1 = next(b for b in blast if b["depth"] == 1)
    assert depth1["symbol"] == "get_user_profile"
    assert depth1["file_path"] == "src/service.py"

    depth2 = next(b for b in blast if b["depth"] == 2)
    assert depth2["symbol"] == "handle_request"
    assert depth2["file_path"] == "src/controller.py"


if __name__ == "__main__":
    test_python_ast_anti_patterns()
    test_javascript_ast_anti_patterns()
    test_symbol_extraction_and_complexity()
    test_symbol_graph_blast_radius()
    print("All AST engine tests passed successfully!")
