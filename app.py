import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from github_sync import backup_to_github, restore_from_github

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devkey")

# Database path
DB_NAME = "library.db"

# ------------------ Database Helpers ------------------ #
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT NOT NULL,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT DEFAULT 'Available',
            taken_by TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# ------------------ Initialize DB + GitHub Sync ------------------ #
init_db()
restore_from_github()

# ------------------ Routes ------------------ #
@app.route("/")
def book_list():
    books = query_db("SELECT * FROM books")
    return render_template("book_list.html", books=books)

@app.route("/add", methods=["POST"])
def add_book():
    serial = request.form["serial"]
    name = request.form["name"]
    author = request.form["author"]
    query_db(
        "INSERT INTO books (serial, name, author, status, taken_by) VALUES (?, ?, ?, 'Available', NULL)",
        (serial, name, author),
    )
    backup_to_github()
    return redirect(url_for("book_list"))

@app.route("/issue", methods=["GET", "POST"])
def issue_book():
    if request.method == "POST":
        book_id = request.form["book"]
        user = request.form["user"]
        query_db(
            "UPDATE books SET status='Issued', taken_by=? WHERE id=?", (user, book_id)
        )
        backup_to_github()
        return redirect(url_for("issued_books"))

    books = query_db("SELECT * FROM books WHERE status='Available'")
    return render_template("issue_book.html", books=books)

@app.route("/issued")
def issued_books():
    books = query_db("SELECT * FROM books WHERE status='Issued'")
    return render_template("issued_books.html", books=books)

@app.route("/return/<int:book_id>")
def return_book(book_id):
    query_db(
        "UPDATE books SET status='Available', taken_by=NULL WHERE id=?", (book_id,)
    )
    backup_to_github()
    return redirect(url_for("issued_books"))

# ------------------ Run App ------------------ #
if __name__ == "__main__":
    app.run(debug=True)
