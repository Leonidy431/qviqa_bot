"""SQLite storage: users, keywords, per-user sources, delivered links.

Ports the original bot's flat-file/global-variable state (add_user,
add_words, add_del_site, checked links list, balance) onto a real schema.
"""

from __future__ import annotations

import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,
    paid_until  INTEGER NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS keywords (
    user_id INTEGER NOT NULL,
    word    TEXT NOT NULL,
    UNIQUE (user_id, word)
);
CREATE TABLE IF NOT EXISTS user_sites (
    user_id INTEGER NOT NULL,
    source  TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE (user_id, source)
);
CREATE TABLE IF NOT EXISTS sent (
    user_id  INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    sent_at  INTEGER NOT NULL,
    UNIQUE (user_id, item_key)
);
"""

DAY = 86400


class Database:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # -- users ------------------------------------------------------------
    def add_user(self, user_id: int, username: str, test_days: int) -> bool:
        """Register a user; returns True if the user is new."""
        now = int(time.time())
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, created_at, paid_until)"
            " VALUES (?, ?, ?, ?)",
            (user_id, username, now, now + test_days * DAY),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get_user(self, user_id: int):
        return self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def delete_user(self, user_id: int) -> None:
        for table in ("users", "keywords", "user_sites", "sent"):
            self.conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def set_active(self, user_id: int, active: bool) -> None:
        self.conn.execute("UPDATE users SET active = ? WHERE user_id = ?", (int(active), user_id))
        self.conn.commit()

    def grant_days(self, user_id: int, days: int) -> int:
        """Extend a subscription (port of add_balance); returns new paid_until."""
        now = int(time.time())
        row = self.get_user(user_id)
        base = max(now, row["paid_until"]) if row else now
        paid_until = base + days * DAY
        self.conn.execute(
            "UPDATE users SET paid_until = ? WHERE user_id = ?", (paid_until, user_id)
        )
        self.conn.commit()
        return paid_until

    def is_subscribed(self, user_id: int) -> bool:
        row = self.get_user(user_id)
        return bool(row and row["paid_until"] > time.time())

    def active_users(self) -> list[sqlite3.Row]:
        now = int(time.time())
        return self.conn.execute(
            "SELECT * FROM users WHERE active = 1 AND paid_until > ?", (now,)
        ).fetchall()

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        return {"users": total, "active": len(self.active_users())}

    # -- keywords ---------------------------------------------------------
    def add_keywords(self, user_id: int, words: list[str]) -> int:
        count = 0
        for word in words:
            word = word.strip().lower()
            if not word:
                continue
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO keywords (user_id, word) VALUES (?, ?)",
                (user_id, word),
            )
            count += cur.rowcount
        self.conn.commit()
        return count

    def del_keyword(self, user_id: int, word: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM keywords WHERE user_id = ? AND word = ?",
            (user_id, word.strip().lower()),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def keywords(self, user_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT word FROM keywords WHERE user_id = ? ORDER BY word", (user_id,)
        ).fetchall()
        return [r["word"] for r in rows]

    # -- sites ------------------------------------------------------------
    def toggle_site(self, user_id: int, source: str) -> bool:
        """Flip a source on/off for the user; returns the new state."""
        row = self.conn.execute(
            "SELECT enabled FROM user_sites WHERE user_id = ? AND source = ?",
            (user_id, source),
        ).fetchone()
        currently_enabled = True if row is None else bool(row["enabled"])
        new_state = 0 if currently_enabled else 1
        self.conn.execute(
            "INSERT INTO user_sites (user_id, source, enabled) VALUES (?, ?, ?)"
            " ON CONFLICT (user_id, source) DO UPDATE SET enabled = ?",
            (user_id, source, new_state, new_state),
        )
        self.conn.commit()
        return bool(new_state)

    def site_enabled(self, user_id: int, source: str) -> bool:
        """Sources are opt-out: enabled unless explicitly toggled off."""
        row = self.conn.execute(
            "SELECT enabled FROM user_sites WHERE user_id = ? AND source = ?",
            (user_id, source),
        ).fetchone()
        return True if row is None else bool(row["enabled"])

    # -- dedupe -----------------------------------------------------------
    def mark_sent(self, user_id: int, item_key: str) -> bool:
        """Record delivery; returns False when it was already sent."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO sent (user_id, item_key, sent_at) VALUES (?, ?, ?)",
            (user_id, item_key, int(time.time())),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def purge_sent(self, older_than_days: int = 30) -> int:
        cutoff = int(time.time()) - older_than_days * DAY
        cur = self.conn.execute("DELETE FROM sent WHERE sent_at < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount
