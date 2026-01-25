# Python file with SQL injection and database issues
# ISSUE COUNT: 7 issues

import sqlite3

# Issue 1: SQL Injection vulnerability (SECURITY - HIGH)
def get_user_by_id(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    cursor.execute(query)
    return cursor.fetchone()

# Issue 2: SQL Injection with f-string (SECURITY - HIGH)
def search_users(search_term):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name LIKE '%{search_term}%'")
    return cursor.fetchall()

# Issue 3: Connection not closed (CORRECTNESS - MEDIUM)
def insert_user(name, email):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    # Connection never closed!

# Issue 4: No error handling (CORRECTNESS - MEDIUM)
def delete_user(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# Issue 5: Cyclomatic complexity too high (COMPLEXITY - MEDIUM)
def process_user_data(user):
    if user is None:
        return None
    if user.get("status") == "active":
        if user.get("role") == "admin":
            if user.get("permissions"):
                if "write" in user.get("permissions"):
                    if user.get("verified"):
                        if user.get("email_confirmed"):
                            return "full_access"
                        else:
                            return "limited_access"
                    else:
                        return "pending_verification"
                else:
                    return "read_only"
            else:
                return "no_permissions"
        else:
            return "standard_user"
    else:
        return "inactive"

# Issue 6: Magic numbers (READABILITY - LOW)
def calculate_user_score(posts, comments, likes):
    return posts * 10 + comments * 5 + likes * 2

# Issue 7: Single letter variable names (READABILITY - LOW)
def update_stats(u, p, c):
    u["posts"] = p
    u["comments"] = c
    return u
