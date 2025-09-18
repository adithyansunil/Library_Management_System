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
FILE_PATH = "books.csv"

if not GITHUB_TOKEN:
    raise Exception("❌ Missing GITHUB_TOKEN environment variable. Please set it before running the app.")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# --------------------------
# Backup SQLite -> GitHub CSV
# --------------------------
def backup_to_github(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM books")
    rows = cur.fetchall()
    conn.close()

    # Write rows to a local CSV
    with open(FILE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "serial", "name", "author", "status", "taken_by"])
        writer.writerows(rows)

    # Upload CSV to GitHub
    with open(FILE_PATH, "rb") as f:
        content = f.read()

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

    # Get SHA if file exists
    sha = None
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json().get("sha")

    data = {
        "message": "🔄 Backup books.csv from SQLite",
        "content": base64.b64encode(content).decode("utf-8"),
    }
    if sha:
        data["sha"] = sha

    r = requests.put(url, headers=headers, json=data)
    if r.status_code not in [200, 201]:
        raise Exception(f"❌ Failed to upload file: {r.status_code} - {r.text}")
    print("✅ Backup successful → books.csv uploaded to GitHub")

# --------------------------
# Restore GitHub CSV -> SQLite
# --------------------------
def restore_from_github(db_path):
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print("⚠️ No books.csv found in GitHub, skipping restore.")
        return

    content = base64.b64decode(r.json()["content"])
    lines = content.decode("utf-8").splitlines()

    reader = csv.DictReader(lines)
    rows = list(reader)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure table exists
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

    # Clear existing rows
    cur.execute("DELETE FROM books")

    # Insert from CSV
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO books (id, serial, name, author, status, taken_by) VALUES (?, ?, ?, ?, ?, ?)",
            (
                row.get("id"),
                row.get("serial"),
                row.get("name"),
                row.get("author"),
                row.get("status", "Available"),
                row.get("taken_by") if "taken_by" in row else None
            )
        )


    conn.commit()
    conn.close()
    print("✅ Restore successful → SQLite updated from books.csv")
