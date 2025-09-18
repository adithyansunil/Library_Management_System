# github_sync.py

import os
import base64
import requests

# Load token and repo details from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "AdithyanSunil"  # <-- replace with your GitHub username
REPO_NAME = "Library_Management_System"
FILE_PATH = "books.csv"

API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


def read_books_csv():
    """
    Fetch the books.csv file from GitHub and return its content as text.
    """
    response = requests.get(API_URL, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content
    elif response.status_code == 404:
        # If the file does not exist, create an empty one
        write_books_csv("Serial,Book Name,Author,Status\n", "Initial commit")
        return "Serial,Book Name,Author,Status\n"
    else:
        raise Exception(f"Failed to fetch file: {response.status_code} - {response.text}")


def write_books_csv(content, message="Update books.csv"):
    """
    Push new content to books.csv on GitHub.
    """
    # Get the SHA of the existing file (required by GitHub API to update)
    get_resp = requests.get(API_URL, headers=HEADERS)
    sha = None
    if get_resp.status_code == 200:
        sha = get_resp.json()["sha"]

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded_content,
        "branch": "main",  # make sure your repo uses 'main' branch
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(API_URL, headers=HEADERS, json=payload)

    if put_resp.status_code not in (200, 201):
        raise Exception(f"Failed to update file: {put_resp.status_code} - {put_resp.text}")

    return True
