from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
import os

app = Flask(__name__)
DB_NAME = "library.db"
CSV_FILE = "books.csv"

# ---- Database Setup ----
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        serial TEXT UNIQUE,
                        name TEXT,
                        author TEXT,
                        status TEXT,
                        taken_by TEXT
                    )''')
        conn.commit()

# ---- CSV Sync ----
def sync_to_csv():
    with sqlite3.connect(DB_NAME) as conn, open(CSV_FILE, "w", newline="") as f:
        c = conn.cursor()
        writer = csv.writer(f)
        writer.writerow(["Serial", "Book Name", "Author", "Status", "Taken By"])
        for row in c.execute("SELECT serial, name, author, status, taken_by FROM books"):
            writer.writerow(row)

def load_from_csv():
    if os.path.exists(CSV_FILE):
        with sqlite3.connect(DB_NAME) as conn, open(CSV_FILE, "r") as f:
            c = conn.cursor()
            reader = csv.DictReader(f)
            for row in reader:
                c.execute("INSERT OR IGNORE INTO books (serial, name, author, status, taken_by) VALUES (?, ?, ?, ?, ?)",
                          (row["Serial"], row["Book Name"], row["Author"], row["Status"], row["Taken By"]))
            conn.commit()

# ---- Routes ----
@app.route("/")
def book_list():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM books")
        books = c.fetchall()
    return render_template("book_list.html", books=books)

@app.route("/add_book", methods=["POST"])
def add_book():
    serial = request.form["serial"]
    name = request.form["name"]
    author = request.form["author"]
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO books (serial, name, author, status, taken_by) VALUES (?, ?, ?, 'Available', '')",
                  (serial, name, author))
        conn.commit()
    sync_to_csv()
    return redirect(url_for("book_list"))

@app.route("/issue", methods=["GET", "POST"])
def issue_book():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if request.method == "POST":
            book_id = request.form["book"]
            user = request.form["user"]
            c.execute("UPDATE books SET status='Issued', taken_by=? WHERE id=?", (user, book_id))
            conn.commit()
            sync_to_csv()
            return redirect(url_for("issued_books"))
        c.execute("SELECT * FROM books WHERE status='Available'")
        available_books = c.fetchall()
    return render_template("issue_book.html", books=available_books)

@app.route("/issued")
def issued_books():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM books WHERE status='Issued'")
        issued = c.fetchall()
    return render_template("issued_books.html", books=issued)

@app.route("/return/<int:book_id>")
def return_book(book_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE books SET status='Available', taken_by='' WHERE id=?", (book_id,))
        conn.commit()
    sync_to_csv()
    return redirect(url_for("issued_books"))

if __name__ == "__main__":
    init_db()
    load_from_csv()
    app.run(debug=True)
