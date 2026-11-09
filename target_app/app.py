# =============================================================================
#  INTENTIONALLY VULNERABLE PRACTICE APP  --  DO NOT DEPLOY PUBLICLY. EVER.
# -----------------------------------------------------------------------------
#  This tiny Flask app contains ON-PURPOSE security bugs (SQL injection) so that
#  students can practice finding and exploiting them with an automated agent.
#  It is the same idea as OWASP Juice Shop or the PortSwigger Web Security Labs:
#  a safe, broken-by-design target that runs only on your own machine.
#
#  It binds to 127.0.0.1 (localhost) only, so nobody else on the network can
#  reach it. Never put this code on a public server or the internet.
# =============================================================================

import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# We keep the whole database in memory so nothing is written to disk and the
# app resets to a clean state every time you restart it.
# check_same_thread=False lets Flask's dev server share this one connection.
db = sqlite3.connect(":memory:", check_same_thread=False)


def seed_database():
    """Create the tables and fill them with a little fake data on startup."""
    cur = db.cursor()

    # --- users table ---------------------------------------------------------
    cur.execute(
        "CREATE TABLE users ("
        "  id INTEGER PRIMARY KEY,"
        "  username TEXT,"
        "  password TEXT,"
        "  role TEXT"
        ")"
    )
    users = [
        ("admin", "supersecret", "admin"),
        ("alice", "password123", "user"),
        ("bob", "hunter2", "user"),
    ]
    cur.executemany(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        users,
    )

    # --- products table ------------------------------------------------------
    # "hidden" = 1 means the product should NOT normally show up in search.
    cur.execute(
        "CREATE TABLE products ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT,"
        "  price REAL,"
        "  hidden INTEGER"
        ")"
    )
    products = [
        ("Sticker Pack", 3.0, 0),
        ("Club T-Shirt", 15.0, 0),
        ("Coffee Mug", 8.0, 0),
        ("SECRET Prototype Badge", 999.0, 1),  # hidden on purpose
    ]
    cur.executemany(
        "INSERT INTO products (name, price, hidden) VALUES (?, ?, ?)",
        products,
    )

    db.commit()


@app.route("/")
def home():
    """A tiny help page so you can see the app is running."""
    return jsonify(
        {
            "message": "Vulnerable practice app. Localhost only. Do not deploy.",
            "routes": {
                "POST /login": "JSON body: {\"username\": ..., \"password\": ...}",
                "GET /search": "query param: ?q=...",
            },
        }
    )


@app.route("/login", methods=["POST"])
def login():
    """
    Log a user in.

    !!! VULNERABLE ON PURPOSE !!!
    The username and password are pasted straight into the SQL string. That
    means a crafted input like   ' OR '1'='1   changes the meaning of the query
    and logs you in without knowing a real password. The correct fix would be
    to use parameized queries (the ? placeholders used in seed_database above).
    """
    body = request.get_json(silent=True) or {}
    username = body.get("username", "")
    password = body.get("password", "")

    # BUG: user input is concatenated directly into the query.
    query = (
        "SELECT id, username, role FROM users "
        "WHERE username = '" + username + "' "
        "AND password = '" + password + "'"
    )

    cur = db.cursor()
    try:
        cur.execute(query)
    except sqlite3.Error as exc:
        # We echo the SQL error back so students can see what the DB complained
        # about. (Leaking errors like this is also bad in real apps!)
        return jsonify({"ok": False, "error": str(exc), "query": query}), 400

    row = cur.fetchone()
    if row:
        return jsonify(
            {"ok": True, "user": {"id": row[0], "username": row[1], "role": row[2]}}
        )
    return jsonify({"ok": False, "error": "invalid credentials"}), 401


@app.route("/search", methods=["GET"])
def search():
    """
    Search products by name.

    !!! VULNERABLE ON PURPOSE !!!
    Same mistake as /login: the search term is concatenated into the SQL. The
    query tries to hide secret products with "hidden = 0", but an attacker can
    inject SQL to reveal the hidden rows anyway.
    """
    q = request.args.get("q", "")

    # BUG: user input is concatenated directly into the query.
    query = (
        "SELECT id, name, price, hidden FROM products "
        "WHERE hidden = 0 AND name LIKE '%" + q + "%'"
    )

    cur = db.cursor()
    try:
        cur.execute(query)
    except sqlite3.Error as exc:
        return jsonify({"ok": False, "error": str(exc), "query": query}), 400

    rows = cur.fetchall()
    results = [
        {"id": r[0], "name": r[1], "price": r[2], "hidden": r[3]} for r in rows
    ]
    return jsonify({"ok": True, "results": results})


# DEMO ONLY: fake configuration, never actual credentials.
@app.route("/debug/config")
def debug_config():
    """Intentionally exposes internal configuration without authentication."""
    return jsonify({"database_host": "internal-db.demo.invalid", "api_key": "DEMO_NOT_A_REAL_SECRET"})


@app.route("/public-config/<path:filename>")
def public_config(filename):
    """Intentionally serves the demo configuration directory publicly."""
    return send_from_directory(str(Path(__file__).resolve().parent / "demo_config"), filename)


if __name__ == "__main__":
    seed_database()
    # Bind to localhost only and keep debug OFF so no interactive debugger /
    # code-execution console is exposed.
    app.run(host="127.0.0.1", port=5000, debug=False)
