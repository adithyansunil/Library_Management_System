import os
import threading
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from github_sync import backup_to_github, restore_from_github
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash


# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devkey")
app.config["SESSION_PERMANENT"] = False

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
def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)


    # Books table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial TEXT UNIQUE,
        name TEXT NOT NULL,
        author TEXT NOT NULL,
        category_id INTEGER,
        status TEXT DEFAULT 'Available',
        taken_by INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (taken_by) REFERENCES users(id)
    )
    """)

    # Transactions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        return_date TEXT,
        FOREIGN KEY (book_id) REFERENCES books(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

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
# Startup
# --------------------------
init_db()
restore_from_github(DATABASE)  # restore DB from GitHub on startup

def async_backup():
    threading.Thread(target=backup_to_github, args=(DATABASE,)).start()
# --------------------------
# Routes
# --------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            conn.close()
            flash("⚠️ Username already taken, please choose another.", "danger")
            return redirect(url_for("register"))
        hashed_password = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()

        #backup_to_github(DATABASE)   # ✅ backup users.csv after new registration
        async_backup()  # instead of backup_to_github(DATABASE)

        flash("✅ Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for("issue_book"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


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
        #backup_to_github(DATABASE)  # sync change
        async_backup()  # instead of backup_to_github(DATABASE)

    except sqlite3.IntegrityError:
        flash("⚠️ Serial number already exists!", "error")
    #backup_to_github(DATABASE)
    async_backup()

    return redirect(url_for("book_list"))

@app.route("/issue_book", methods=["GET", "POST"])
def issue_book():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    if request.method == "POST":
        serial = request.form["serial"]
        issued_to = request.form["issued_to"]  # if you added textbox
        user_id = session["user_id"]

        cur.execute("SELECT id FROM books WHERE serial=? AND status='Available'", (serial,))
        book = cur.fetchone()

        if book:
            book_id = book[0]
            cur.execute("SELECT username FROM users WHERE id=?", (user_id,))
            row = cur.fetchone()
            username = row[0] if row else None
            cur.execute("UPDATE books SET status='Issued', taken_by=? WHERE id=?", (username, book_id))
            cur.execute("INSERT INTO transactions (book_id, user_id, issue_date) VALUES (?, ?, datetime('now'))",
                        (book_id, user_id))
            conn.commit()

            #backup_to_github(DATABASE)   # ✅ backup books.csv after issue
            async_backup()  # instead of backup_to_github(DATABASE)


            flash("Book issued successfully!", "success")
        else:
            flash("Book not available.", "danger")

    cur.execute("SELECT * FROM books WHERE status='Available'")
    books = [dict(id=row[0], serial=row[1], name=row[2], author=row[3]) for row in cur.fetchall()]
    conn.close()

    return render_template("issue_book.html", books=books)


@app.route("/issued_books", methods=["GET", "POST"])
def issued_books():
    #if "user_id" not in session:
    #    flash("Please login first.", "warning")
     #   return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Fetch only issued books
    cur.execute("""
        SELECT b.id, b.serial, b.name, b.author, b.taken_by
        FROM books b
        WHERE b.status = 'Issued'
    """)
    rows = cur.fetchall()

    books = [dict(id=row[0], serial=row[1], name=row[2], author=row[3], taken_by=row[4]) for row in rows]

    conn.close()
    return render_template("issued_books.html", books=books)



@app.route("/return_book/<int:book_id>", methods=["POST"])
def return_book(book_id):
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Get the username of the logged-in user
    cur.execute("SELECT username FROM users WHERE id=?", (session["user_id"],))
    row = cur.fetchone()
    username = row[0] if row else None

    # Check if the book exists and is taken by this user
    cur.execute("SELECT taken_by FROM books WHERE id=?", (book_id,))
    row = cur.fetchone()

    if row and row[0] == username:  # ✅ only same user can return
        cur.execute("UPDATE books SET status='Available', taken_by=NULL WHERE id=?", (book_id,))
        cur.execute("UPDATE transactions SET return_date=datetime('now') WHERE book_id=? AND user_id=? AND return_date IS NULL",
                    (book_id, session["user_id"]))
        conn.commit()

        #backup_to_github(DATABASE)   # ✅ backup after return
        async_backup()  # instead of backup_to_github(DATABASE)


        flash("Book returned successfully!", "success")
    else:
        flash("❌ You cannot return this book. It was issued by another user.", "danger")

    conn.close()
    return redirect(url_for("issued_books"))







# --------------------------
# Run
# --------------------------
if __name__ == "__main__":
    app.run(debug=True)
