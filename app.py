import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from github_sync import backup_to_github, restore_from_github

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devkey")

DATABASE = "library.db"

# --------------------------
# Database helper functions
# --------------------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available',
                taken_by TEXT
            )
        """)
        conn.commit()

def query_db(query, args=(), one=False):
    with get_db() as conn:
        cur = conn.execute(query, args)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows

def execute_db(query, args=()):
    with get_db() as conn:
        cur = conn.execute(query, args)
        conn.commit()
        return cur.lastrowid

# --------------------------
# Routes
# --------------------------
@app.route("/")
def book_list():
    books = query_db("SELECT * FROM books")
    return render_template("book_list.html", books=books)

@app.route("/add_book", methods=["POST"])
def add_book():
    serial = request.form["serial"]
    name = request.form["name"]
    author = request.form["author"]

    try:
        execute_db(
            "INSERT INTO books (serial, name, author, status) VALUES (?, ?, ?, 'Available')",
            (serial, name, author)
        )
        flash("✅ Book added successfully!", "success")
        backup_to_github(DATABASE)  # sync change
    except sqlite3.IntegrityError:
        flash("⚠️ Serial number already exists!", "error")

    return redirect(url_for("book_list"))

@app.route("/issue", methods=["GET", "POST"])
def issue_book():
    if request.method == "POST":
        book_id = request.form["book"]   # ✅ now matches <select name="book">
        user = request.form["user"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE books SET status = ?, taken_by = ? WHERE id = ?", ("Issued", user, book_id))
        conn.commit()
        conn.close()

        backup_to_github(DATABASE)  # save to GitHub
        return redirect(url_for("issued_books"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books")
    books = cur.fetchall()
    conn.close()

    return render_template("issue_book.html", books=books)


@app.route("/issued")
def issued_books():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE status = 'Issued'")
    books = cur.fetchall()
    conn.close()
    return render_template("issued_books.html", books=books)

@app.route("/return/<int:book_id>", methods=["POST"])
def return_book(book_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE books SET status = 'Available', taken_by = NULL WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()

    backup_to_github(DATABASE)
    return redirect(url_for("issued_books"))

# --------------------------
# Startup
# --------------------------
init_db()
restore_from_github(DATABASE)  # restore DB from GitHub on startup

# --------------------------
# Run
# --------------------------
if __name__ == "__main__":
    app.run(debug=True)
