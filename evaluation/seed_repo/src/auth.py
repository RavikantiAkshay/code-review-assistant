# Python file with intentional security and code quality issues
# ISSUE COUNT: 8 issues

import os
import hashlib

# Issue 1: Hardcoded credentials (SECURITY - HIGH)
DATABASE_PASSWORD = "admin123"
API_SECRET_KEY = "sk_live_abcd1234567890"

# Issue 2: Weak password hashing (SECURITY - HIGH)
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

# Issue 3: Missing input validation (SECURITY - MEDIUM)
def authenticate(username, password):
    # No validation of inputs
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return query

# Issue 4: Insecure eval usage (SECURITY - HIGH)
def execute_user_code(code_string):
    result = eval(code_string)
    return result

# Issue 5: Unused import (READABILITY - LOW)
import sys

# Issue 6: Missing docstring (READABILITY - LOW)
def validate_token(token):
    if token == API_SECRET_KEY:
        return True
    return False

# Issue 7: Too broad exception (CORRECTNESS - MEDIUM)
def load_config():
    try:
        with open("config.json") as f:
            return f.read()
    except:
        return None

# Issue 8: Mutable default argument (CORRECTNESS - MEDIUM)
def add_user(users_list=[]):
    users_list.append("new_user")
    return users_list
