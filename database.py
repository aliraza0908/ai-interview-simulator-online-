"""
database.py — SQLite database setup and all data-access functions.
Database file: data/app.db (auto-created on first run).
"""

import sqlite3
import bcrypt
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")


def _get_conn():
    """Return a new SQLite connection with row_factory set for dict-like access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't already exist. Call once at app startup."""
    conn = _get_conn()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                email           TEXT    NOT NULL UNIQUE,
                password_hash   TEXT    NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                cv_filename     TEXT,
                average_score   REAL,
                persona_key     TEXT,
                interview_type_key TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Safe migration for DBs created before persona/interview_type columns existed.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(interviews)")}
        if "persona_key" not in existing_cols:
            conn.execute("ALTER TABLE interviews ADD COLUMN persona_key TEXT")
        if "interview_type_key" not in existing_cols:
            conn.execute("ALTER TABLE interviews ADD COLUMN interview_type_key TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interview_responses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id    INTEGER NOT NULL REFERENCES interviews(id),
                question_number INTEGER NOT NULL,
                question_text   TEXT    NOT NULL,
                answer_text     TEXT,
                score           INTEGER,
                feedback        TEXT,
                missing_keywords TEXT
            )
        """)
    conn.close()


# ─────────────────────────────────────────────
# USER AUTH
# ─────────────────────────────────────────────

class DuplicateEmailError(Exception):
    pass


def create_user(name: str, email: str, password: str) -> int:
    """
    Hash password with bcrypt, insert new user row.
    Returns the new user's id.
    Raises DuplicateEmailError if email already registered.
    """
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = _get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name.strip(), email.strip().lower(), password_hash),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise DuplicateEmailError(f"Email '{email}' is already registered.")
    finally:
        conn.close()


def verify_user(email: str, password: str) -> dict | None:
    """
    Check email exists and bcrypt password matches.
    Returns user dict (id, name, email) or None on failure.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return None
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def get_user_by_email(email: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# INTERVIEW STORAGE
# ─────────────────────────────────────────────

def save_interview(
    user_id: int,
    cv_filename: str,
    responses_list: list,
    persona_key: str = None,
    interview_type_key: str = None,
) -> int:
    """
    Insert one interview row + all response rows.
    responses_list: list of dicts with keys:
        question_number, question_text, answer_text,
        score, feedback, missing_keywords (list or str)
    Returns the new interview_id.
    """
    scores = [r["score"] for r in responses_list if r.get("score") is not None]
    avg = round(sum(scores) / len(scores), 2) if scores else None

    conn = _get_conn()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO interviews
                   (user_id, cv_filename, average_score, persona_key, interview_type_key)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, cv_filename, avg, persona_key, interview_type_key),
            )
            interview_id = cur.lastrowid

            for r in responses_list:
                kw = r.get("missing_keywords", "")
                if isinstance(kw, list):
                    kw = ", ".join(kw)
                conn.execute(
                    """INSERT INTO interview_responses
                       (interview_id, question_number, question_text,
                        answer_text, score, feedback, missing_keywords)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        interview_id,
                        r["question_number"],
                        r["question_text"],
                        r.get("answer_text", ""),
                        r.get("score"),
                        r.get("feedback", ""),
                        kw,
                    ),
                )
        return interview_id
    finally:
        conn.close()


def get_user_interview_history(user_id: int) -> list:
    """
    Return list of past interviews for the user (most recent first).
    Each item: {id, cv_filename, average_score, persona_key, interview_type_key, created_at}
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, cv_filename, average_score, persona_key, interview_type_key, created_at
               FROM interviews WHERE user_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_interview_responses(interview_id: int) -> list:
    """Return all response rows for a given interview."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM interview_responses
               WHERE interview_id = ? ORDER BY question_number""",
            (interview_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
