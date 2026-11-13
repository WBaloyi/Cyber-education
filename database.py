"""SQLite storage for testimonials, contact messages and enrollments.

The database file is created next to this module on first run. Data from the
old JSON files (new-testimonials.json, submissions.json) is imported once; the
JSON files are left untouched as a backup.
"""
import json
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).parent
DATABASE_FILE = BASE_DIR / "cyber_education.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS testimonials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    message TEXT NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contact_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    course_of_interest TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_slug TEXT NOT NULL,
    intake_date TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (course_slug, intake_date, email)
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Testimonials that used to be hard-coded in the About page.
BUILT_IN_TESTIMONIALS = [
    ("Shawn Modise", "After using Cyber Education for a few months, I can positively say it has been worth the investment. I can take classes at my own pace and access learning resources around my full-time job."),
    ("Abigail Brown", "This platform helped me broaden my IT knowledge and skills. I would definitely recommend it to others!"),
    ("Kenji Tanaka", "Cyber Education helped me balance my personal schedule, my children's schedule, and work through flexible remote learning."),
    ("Thembi Ndlovu", "The online courses, videos, and assessments gave me the practical experience I needed to succeed in the IT industry."),
    ("Radhika Bala", "I recently started working in the IT industry, and Cyber Education has been incredibly beneficial and innovative."),
]


def connect():
    # isolation_level=None: autocommit, so multi-step writes use explicit BEGIN IMMEDIATE.
    connection = sqlite3.connect(DATABASE_FILE, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def _read_json_list(file_name):
    try:
        with (BASE_DIR / file_name).open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def init_db():
    connection = connect()
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        _rename_old_tables(connection)
        connection.executescript(SCHEMA)
        already_imported = connection.execute(
            "SELECT 1 FROM app_meta WHERE key = 'json_imported'").fetchone()
        if not already_imported:
            _import_initial_data(connection)
    finally:
        connection.close()


def _rename_old_tables(connection):
    """Databases created before the US-spelling change used an 'enrolments' table."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "enrolments" not in tables:
        return
    if "enrollments" not in tables:
        connection.execute("ALTER TABLE enrolments RENAME TO enrollments")
        return
    # Both exist: move any old rows across, then drop the old table.
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT OR IGNORE INTO enrollments (course_slug, intake_date, name, email, created_at) "
            "SELECT course_slug, intake_date, name, email, created_at FROM enrolments")
        connection.execute("DROP TABLE enrolments")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _import_initial_data(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        seen = set()
        for name, message in BUILT_IN_TESTIMONIALS:
            connection.execute(
                "INSERT INTO testimonials (name, message, rating, approved) VALUES (?, ?, 5, 1)",
                (name, message))
            seen.add((name.lower(), message.lower()))

        # Earlier submissions were shown publicly already, so they stay approved (no rating was collected).
        for item in _read_json_list("new-testimonials.json"):
            name = str(item.get("name", "")).strip() if isinstance(item, dict) else ""
            message = str(item.get("message", "")).strip() if isinstance(item, dict) else ""
            if not name or not message or (name.lower(), message.lower()) in seen:
                continue
            seen.add((name.lower(), message.lower()))
            connection.execute(
                "INSERT INTO testimonials (name, message, approved) VALUES (?, ?, 1)", (name, message))

        for item in _read_json_list("submissions.json"):
            if not isinstance(item, dict):
                continue
            connection.execute(
                "INSERT INTO contact_submissions (name, email, course_of_interest, message) VALUES (?, ?, ?, ?)",
                (str(item.get("name", "")).strip(), str(item.get("email", "")).strip(),
                 str(item.get("courseOfIntrest", "")).strip(), str(item.get("message", "")).strip()))

        connection.execute("INSERT INTO app_meta (key, value) VALUES ('json_imported', '1')")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
