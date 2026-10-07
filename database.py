import json
import os
import sqlite3
from pathlib import Path

# The database is a single file. By default it sits next to this script,
# but the BUGLENS_DB environment variable can point it somewhere else.
DB_PATH = Path(os.environ.get("BUGLENS_DB", Path(__file__).parent / "buglens.db"))


def get_connection():
    """Open a connection to the SQLite file.

    row_factory = sqlite3.Row lets us read columns by name (row["title"])
    instead of by position (row[1]).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the bugs table if it doesn't exist yet. Safe to run every startup."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bugs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                raw_report  TEXT NOT NULL DEFAULT '',
                priority    TEXT NOT NULL DEFAULT 'medium',
                status      TEXT NOT NULL DEFAULT 'open',
                environment TEXT NOT NULL DEFAULT '',
                steps       TEXT NOT NULL DEFAULT '[]',
                expected    TEXT NOT NULL DEFAULT '',
                actual      TEXT NOT NULL DEFAULT '',
                labels      TEXT NOT NULL DEFAULT '[]',
                assignee    TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


# Example bugs, loaded when the database is empty so the app never looks blank
# (useful on free hosting, where the database is wiped on every restart).
DEMO_BUGS = [
    {
        "title": "Intermittent login session failure on Chrome",
        "raw_report": "The login thing doesn't work sometimes and then I get kicked out, happened twice on Chrome.",
        "priority": "high", "status": "in_progress", "environment": "Chrome",
        "steps": ["Open the login page", "Sign in", "Navigate to the dashboard", "Session unexpectedly expires"],
        "expected": "User remains signed in", "actual": "User is logged out",
        "labels": ["authentication", "session", "chrome"], "assignee": "Priya",
    },
    {
        "title": "Customer charged twice for one order",
        "raw_report": "i got charged twice for my order!!! this is on my iphone, please refund me asap",
        "priority": "critical", "status": "open", "environment": "iPhone",
        "steps": ["Add an item to the cart", "Go through checkout and pay", "Check the card statement"],
        "expected": "The card is charged once", "actual": "The card was charged twice",
        "labels": ["payments", "checkout", "user-report"], "assignee": "",
    },
    {
        "title": "Dashboard loads slowly on Firefox",
        "raw_report": "the app is super slow when i open the dashboard, takes forever to load on firefox windows",
        "priority": "medium", "status": "open", "environment": "Firefox, Windows",
        "steps": ["Sign in", "Open the dashboard", "Wait for it to load"],
        "expected": "The dashboard loads within a couple of seconds", "actual": "The dashboard takes a long time to load",
        "labels": ["performance", "dashboard", "firefox"], "assignee": "Sam",
    },
    {
        "title": "Typo on the About page: \"teh team\"",
        "raw_report": "theres a typo on the about page, it says \"teh team\" instead of \"the team\"",
        "priority": "low", "status": "resolved", "environment": "",
        "steps": ["Open the About page", "Read the team section"],
        "expected": "Text reads \"the team\"", "actual": "Text reads \"teh team\"",
        "labels": ["content", "user-report"], "assignee": "Alex",
    },
    {
        "title": "Submit button misaligned in dark mode",
        "raw_report": "in dark mode the submit button is misaligned and the colour is weird, kinda hard to see",
        "priority": "low", "status": "closed", "environment": "",
        "steps": ["Turn on dark mode", "Open any form", "Look at the Submit button"],
        "expected": "The button is aligned and easy to see", "actual": "The button is misaligned with low contrast",
        "labels": ["ui", "dark-mode"], "assignee": "Sam",
    },
]


def seed_demo_data():
    """Insert the example bugs, but only if there are no bugs at all."""
    with get_connection() as conn:
        if conn.execute("SELECT COUNT(*) FROM bugs").fetchone()[0] > 0:
            return
        for bug in DEMO_BUGS:
            data = {**bug, "steps": json.dumps(bug["steps"]), "labels": json.dumps(bug["labels"])}
            columns = ", ".join(data)
            placeholders = ", ".join("?" for _ in data)
            conn.execute(f"INSERT INTO bugs ({columns}) VALUES ({placeholders})", list(data.values()))


def row_to_dict(row):
    """Convert a database row into a plain dict.

    SQLite has no list type, so `steps` and `labels` are stored as JSON text
    and turned back into Python lists here.
    """
    bug = dict(row)
    bug["steps"] = json.loads(bug["steps"])
    bug["labels"] = json.loads(bug["labels"])
    return bug
