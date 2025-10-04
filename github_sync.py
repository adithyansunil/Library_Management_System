import os
import base64
import requests
import sqlite3
import csv

# --------------------------
# GitHub Repo Settings
# --------------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "adithyansunil/Library_Management_System"

if not GITHUB_TOKEN:
    raise Exception("❌ Missing GITHUB_TOKEN environment variable. Please set it before running the app.")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# --------------------------
# GitHub Helpers
# --------------------------
def upload_to_github(file_path, message):
    """Upload a file to GitHub repo"""
    with open(file_path, "rb") as f:
        content = f.read()

    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"

    # Always fetch latest SHA to avoid 409 conflict
    resp = requests.get(url, headers=headers)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    data = {
        "message": message,
        "content": base64.b64encode(content).decode("utf-8"),
    }
    if sha:
        data["sha"] = sha

    r = requests.put(url, headers=headers, json=data)

    if r.status_code not in [200, 201]:
        raise Exception(f"❌ Failed to upload {file_path}: {r.status_code} - {r.text}")

    print(f"✅ {file_path} uploaded to GitHub")


def download_from_github(file_path):
    """Download file content from GitHub repo."""
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"⚠️ No {file_path} found in GitHub, skipping restore.")
        return None
    content = base64.b64decode(r.json()["content"])
    return content.decode("utf-8").splitlines()

# --------------------------
# Backup Functions
# --------------------------
def backup_books(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 🔑 CHANGE 1: Explicitly select only the 6 required columns
    cur.execute("SELECT id, serial, name, author, status, taken_by FROM books")
    rows = cur.fetchall()
    conn.close()

    file_path = "books.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "serial", "name", "author", "status", "taken_by"])
        writer.writerows(rows)

    upload_to_github(file_path, "🔄 Backup books.csv from SQLite")


def backup_users(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # 🔑 CHANGE 2: Explicitly select needed columns
    cur.execute("SELECT id, username, password FROM users")
    rows = cur.fetchall()
    conn.close()

    file_path = "users.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "username", "password"])
        writer.writerows(rows)

    upload_to_github(file_path, "🔄 Backup users.csv from SQLite")

# --------------------------
# Restore Functions
# --------------------------
def restore_books(db_path):
    lines = download_from_github("books.csv")
    if not lines:
        return

    reader = csv.DictReader(lines)
    rows = list(reader)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            taken_by TEXT
        )
    """)

    cur.execute("DELETE FROM books")

    # 🔑 CHANGE 3: Use safe default values (avoid blank status/taken_by)
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO books (id, serial, name, author, status, taken_by) VALUES (?, ?, ?, ?, ?, ?)",
            (
                row.get("id"),
                row.get("serial"),
                row.get("name"),
                row.get("author"),
                row.get("status") or "Available",   # default if blank
                row.get("taken_by") or None         # default if blank
            ),
        )

    conn.commit()
    conn.close()
    print("✅ Restore successful → SQLite updated from books.csv")


def restore_users(db_path):
    lines = download_from_github("users.csv")
    if not lines:
        return

    reader = csv.DictReader(lines)
    rows = list(reader)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cur.execute("DELETE FROM users")

    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO users (id, username, password) VALUES (?, ?, ?)",
            (
                row.get("id"),
                row.get("username"),
                row.get("password"),
            ),
        )

    conn.commit()
    conn.close()
    print("✅ Restore successful → SQLite updated from users.csv")

# --------------------------
# Master Functions
# --------------------------
def backup_to_github(db_path):
    backup_books(db_path)
    backup_users(db_path)

def restore_from_github(db_path):
    restore_books(db_path)
    restore_users(db_path)
