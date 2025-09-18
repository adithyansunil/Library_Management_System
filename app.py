from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import csv
import os
from github_sync import read_books_csv, write_books_csv

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_FILE = "library.db"


# ------------------------
# Database Helpers
# ------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS books (
            serial TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            taken_by TEXT
        )
    """)
    conn.commit()
    conn.close()


def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    conn.commit()
    conn.close()
    return (rows[0] if rows else None) if one else rows


# ------------------------
# GitHub Sync Helpers
# ------------------------
def sync_to_github():
    """Export DB to CSV and upload to GitHub"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    rows = c.execute("SELECT serial, name, author, status, taken_by FROM books").fetchall()
    conn.close()

    csv_file = "books.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Serial", "Name", "Author", "Status", "Taken By"])
        writer.writerows(rows)

    write_books_csv(csv_file)  # upload to GitHub


def restore_from_github():
    """If DB is empty, restore from GitHub CSV"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM books")
    count = c.fetchone()[0]
    conn.close()

    if count == 0:
        content = read_books_csv()
        if content:
            lines = content.strip().split("\n")
            reader = csv.DictReader(lines)
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            for row in reader:
                c.execute("INSERT OR IGNORE INTO books VALUES (?, ?, ?, ?, ?)",
                          (row["Serial"], row["Name"], row["Author"], row["Status"], row["Taken By"]))
            conn.commit()
            conn.close()


# ------------------------
# Routes
# ------------------------
@app.route("/")
def book_list():
    books = query_db("SELECT * FROM books")
    return render_template("book_list.html", books=books)


@app.route("/add", methods=["POST"])
def add_book():
    serial = request.form["serial"]
    name = request.form["name"]
    author = request.form["author"]

    exists = query_db("SELECT * FROM books WHERE serial=?", [serial], one=True)
    if exists:
        flash("Book with this serial already exists!", "error")
    else:
        query_db("INSERT INTO books (serial, name, author, status, taken_by) VALUES (?, ?, ?, 'Available', '')",
                 [serial, name, author])
        flash("Book added successfully!", "success")
        sync_to_github()

    return redirect(url_for("book_list"))


@app.route("/issue_book", methods=["GET", "POST"])
def issue_book():
    if request.method == "POST":
        serial = request.form["serial"]
        user = request.form["user"]

        book = query_db("SELECT * FROM books WHERE serial=?", [serial], one=True)
        if book and book["status"] == "Available":
            query_db("UPDATE books SET status='Not Available', taken_by=? WHERE serial=?", [user, serial])
            flash("Book issued successfully!", "success")
            sync_to_github()
        else:
            flash("Book is not available!", "error")

        return redirect(url_for("book_list"))

    books = query_db("SELECT * FROM books")
    return render_template("issue_book.html", books=books)


@app.route("/issued")
def issued_books():
    books = query_db("SELECT * FROM books WHERE status='Not Available'")
    return render_template("issued_books.html", books=books)


@app.route("/return/<serial>", methods=["POST"])
def return_book(serial):
    book = query_db("SELECT * FROM books WHERE serial=?", [serial], one=True)
    if book and book["status"] == "Not Available":
        query_db("UPDATE books SET status='Available', taken_by='' WHERE serial=?", [serial])
        flash("Book returned successfully!", "success")
        sync_to_github()
    else:
        flash("Book not found or already available!", "error")

    return redirect(url_for("issued_books"))


# ------------------------
# Run App
# ------------------------
@app.before_first_request
def initialize():
    init_db()
    restore_from_github()

if __name__ == "__main__":
    app.run(debug=True)
