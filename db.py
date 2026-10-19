"""Database layer: a point log plus deadlines and birthdays, stored in one SQLite file (points.db).

Every point change is its own row in point_log. A member's total is the sum of
their rows, so history, undoing mistakes and leaderboards all come for free.
"""
import sqlite3
import time
from contextlib import closing

DB_PATH = "points.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with closing(_connect()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS point_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      INTEGER NOT NULL,
                reason      TEXT    NOT NULL,
                given_by    INTEGER NOT NULL,
                created_at  INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deadlines (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                due_at      INTEGER NOT NULL,
                description TEXT,
                reminded    INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS birthdays (
                user_id             INTEGER PRIMARY KEY,
                month               INTEGER NOT NULL,
                day                 INTEGER NOT NULL,
                last_announced_year INTEGER
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        _add_missing_columns(conn)


# Columns added to a table after it was first created: (table, column, definition).
# Also put each one in the CREATE TABLE above so new databases get it directly.
# SQLite rules for ADD COLUMN: no PRIMARY KEY or UNIQUE, and NOT NULL needs a DEFAULT,
# which is the value every existing row gets.
ADDED_COLUMNS = [
    ("deadlines", "reminded", "INTEGER NOT NULL DEFAULT 0"),
    ("birthdays", "last_announced_year", "INTEGER"),  # NULL = never announced
]


def _add_missing_columns(conn):
    """Add any ADDED_COLUMNS an older points.db doesn't have yet. Safe to run on every
    startup: existing columns are skipped, and ADD COLUMN never touches existing data."""
    for table, column, definition in ADDED_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"Database: added column {table}.{column}")


# ---------- points ----------

def add_points(user_id, amount, reason, given_by):
    """Log a point change. Use a negative amount to remove points."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO point_log (user_id, amount, reason, given_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, reason, given_by, int(time.time())),
        )


def ranked():
    """All members with any point history as [(rank, user_id, total)], best first.
    Members with the same total share a rank (8, 7, 7, 5 -> ranks 1, 2, 2, 4)."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT user_id, SUM(amount) AS total FROM point_log "
            "GROUP BY user_id ORDER BY total DESC, MIN(created_at) ASC"
        ).fetchall()
    board, rank, prev = [], 0, None
    for position, row in enumerate(rows, start=1):
        if row["total"] != prev:
            rank, prev = position, row["total"]
        board.append((rank, row["user_id"], row["total"]))
    return board


def standing(user_id):
    """(rank, total, number_of_ranked_members), or None if they have no history."""
    board = ranked()
    for rank, uid, total in board:
        if uid == user_id:
            return rank, total, len(board)
    return None


def leader():
    """User ID of the sole #1, or None if empty or tied for first."""
    board = ranked()
    if not board or (len(board) > 1 and board[1][2] == board[0][2]):
        return None
    return board[0][1]


def history(user_id, limit=None):
    sql = (
        "SELECT amount, reason, given_by, created_at FROM point_log "
        "WHERE user_id = ? ORDER BY created_at DESC, id DESC"
    )
    params = [user_id]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with closing(_connect()) as conn:
        return conn.execute(sql, params).fetchall()


def history_count(user_id):
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM point_log WHERE user_id = ?", (user_id,)
        ).fetchone()[0]


# ---------- deadlines ----------

def add_deadline(name, due_at, description):
    """Returns False if a deadline with that name already exists."""
    try:
        with closing(_connect()) as conn, conn:
            conn.execute(
                "INSERT INTO deadlines (name, due_at, description) VALUES (?, ?, ?)",
                (name, due_at, description),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_deadline(name):
    """Returns True if a deadline was deleted."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM deadlines WHERE name = ?", (name,))
        return cur.rowcount > 0


def deadlines_after(timestamp):
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM deadlines WHERE due_at >= ? ORDER BY due_at", (timestamp,)
        ).fetchall()


def deadlines_needing_reminder(now, window_seconds):
    """Deadlines due within the window that haven't been announced yet."""
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM deadlines WHERE reminded = 0 AND due_at > ? AND due_at <= ? "
            "ORDER BY due_at",
            (now, now + window_seconds),
        ).fetchall()


def mark_reminded(deadline_id):
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE deadlines SET reminded = 1 WHERE id = ?", (deadline_id,))


# ---------- birthdays (month and day only, never the year) ----------

def set_birthday(user_id, month, day):
    """Save or change a birthday. Changing the date clears last_announced_year,
    so a corrected birthday still gets its announcement this year."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO birthdays (user_id, month, day) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET month = excluded.month, day = excluded.day, "
            "last_announced_year = CASE WHEN month = excluded.month AND day = excluded.day "
            "THEN last_announced_year ELSE NULL END",
            (user_id, month, day),
        )


def remove_birthday(user_id):
    """Returns True if a birthday was deleted."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM birthdays WHERE user_id = ?", (user_id,))
        return cur.rowcount > 0


def all_birthdays():
    with closing(_connect()) as conn:
        return conn.execute("SELECT * FROM birthdays").fetchall()


def mark_birthday_announced(user_id, year):
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE birthdays SET last_announced_year = ? WHERE user_id = ?", (year, user_id)
        )


# ---------- settings ----------

def get_setting(key):
    with closing(_connect()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key, value):
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
