# Python utility file with complexity and style issues
# ISSUE COUNT: 8 issues

import os
import json
import re

# Issue 1: Unused variable (READABILITY - LOW)
UNUSED_CONSTANT = "this is never used"

# Issue 2: Function too long (COMPLEXITY - MEDIUM)
def process_data(data):
    result = {}
    if data:
        for item in data:
            if item.get("type") == "user":
                result["users"] = result.get("users", [])
                result["users"].append(item)
            elif item.get("type") == "post":
                result["posts"] = result.get("posts", [])
                result["posts"].append(item)
            elif item.get("type") == "comment":
                result["comments"] = result.get("comments", [])
                result["comments"].append(item)
            elif item.get("type") == "like":
                result["likes"] = result.get("likes", [])
                result["likes"].append(item)
            elif item.get("type") == "share":
                result["shares"] = result.get("shares", [])
                result["shares"].append(item)
            elif item.get("type") == "follow":
                result["follows"] = result.get("follows", [])
                result["follows"].append(item)
            elif item.get("type") == "message":
                result["messages"] = result.get("messages", [])
                result["messages"].append(item)
            else:
                result["other"] = result.get("other", [])
                result["other"].append(item)
    return result

# Issue 3: Comparison to None (READABILITY - LOW)
def check_value(val):
    if val == None:
        return False
    return True

# Issue 4: Using type() instead of isinstance() (CORRECTNESS - LOW)
def is_string(value):
    if type(value) == str:
        return True
    return False

# Issue 5: Bare except (CORRECTNESS - MEDIUM)
def safe_divide(a, b):
    try:
        return a / b
    except:
        return 0

# Issue 6: No return type hint (READABILITY - LOW)
def format_name(first, last):
    return f"{first} {last}"

# Issue 7: Global variable modification (CORRECTNESS - MEDIUM)
counter = 0

def increment():
    global counter
    counter += 1
    return counter

# Issue 8: Inefficient string concatenation in loop (COMPLEXITY - LOW)
def build_report(items):
    report = ""
    for item in items:
        report = report + str(item) + "\n"
    return report
