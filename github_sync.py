# github_sync.py

import os
import base64
import requests

# Load token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise Exception("❌ Missing GITHUB_TOKEN environment variable.")

# ⚠️ Must match your GitHub username exactly (case-sensitive!)
REPO_OWNER = "AdithyanSunil"
REPO_NAME = "Library_Management_System"
FILE_PATH = "books.csv"
BRANCH = "main"  # or "master" if your repo uses master

API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


def read_books_csv():
    """Fetch books.csv content from GitHub and return as plain text."""
    response = requests.get(API_URL, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content

    elif response.status_code == 404:
        # Create fresh CSV if missing
        default_csv = "Serial,Book Name,Author,Status,Taken By\n"
        write_books_csv(default_csv, "Initial commit with CSV headers")
        return default_csv

    elif response.status_code == 401:
        raise Exception("❌ GitHub authentication failed. Check your GITHUB_TOKEN.")

    else:
        raise Exception(f"❌ Failed to fetch file: {response.status_code} - {response.text}")


def write_books_csv(content, message="Update books.csv"):
    """Push new content to GitHub (create or update)."""
    # Get current file SHA (required for updates)
    get_resp = requests.get(API_URL, headers=HEADERS)
    sha = None
    if get_resp.status_code == 200:
        sha = get_resp.json()["sha"]

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded_content,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(API_URL, headers=HEADERS, json=payload)

    if put_resp.status_code not in (200, 201):
        raise Exception(f"❌ Failed to update file: {put_resp.status_code} - {put_resp.text}")

    print("✅ books.csv synced successfully to GitHub.")
    return True
