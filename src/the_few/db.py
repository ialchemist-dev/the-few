"""SQLite store for items and their triage state.

One row per item. `link` is UNIQUE, so re-running never creates duplicates.

The triage state machine is the heart of v0 — items flow:

    new  ──(you keep it)────▶  interested   (your reading list; persists)
         ──(you don't)───────▶  dismissed    (archived; never shown again)

`brief` shows `new`. `keep` finalizes a brief: kept items become `interested`,
the rest of that brief become `dismissed`. `list` shows `interested`. A small
`view` table maps the numbers you see (1, 2, 3…) back to item ids so you can say
`keep 1 3` or `open 2`.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import paths

# Triage states.
NEW = "new"
INTERESTED = "interested"
DISMISSED = "dismissed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_slug   TEXT NOT NULL,
    title         TEXT,
    link          TEXT UNIQUE NOT NULL,
    published     TEXT,
    fetched_at    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    full_text     TEXT,
    summary       TEXT,
    summarized_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_slug);

-- Maps the numbers shown in the last brief/list to item ids (rewritten each view).
CREATE TABLE IF NOT EXISTS view (
    pos      INTEGER PRIMARY KEY,
    item_id  INTEGER NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    """Thin wrapper over a SQLite connection with the operations the app needs."""

    def __init__(self, path: str | Path | None = None):
        self.path = str(path) if path else str(paths.db_path())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns missing from older databases (no-op on fresh ones)."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        if "status" not in cols:
            self.conn.execute(
                "ALTER TABLE items ADD COLUMN status TEXT NOT NULL DEFAULT 'new'"
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- ingest -----------------------------------------------------------

    def has_link(self, link: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM items WHERE link = ?", (link,))
        return cur.fetchone() is not None

    def add_item(
        self,
        *,
        source_slug: str,
        title: str,
        link: str,
        full_text: str = "",
        published: str | None = None,
    ) -> int | None:
        """Insert a new item (status 'new'). Returns its id, or None if it existed."""
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO items
                (source_slug, title, link, published, fetched_at, status, full_text)
            VALUES (?, ?, ?, ?, ?, 'new', ?)
            """,
            (source_slug, title, link, published, _now(), full_text),
        )
        self.conn.commit()
        return cur.lastrowid if cur.rowcount else None

    # --- triage / queries -------------------------------------------------

    def items_by_status(self, status: str, limit: int | None = None) -> list[sqlite3.Row]:
        # Newest first by publish date; items without a date sort to the end.
        sql = (
            "SELECT * FROM items WHERE status = ? "
            "ORDER BY (published IS NULL), published DESC, id DESC"
        )
        params: tuple = (status,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (status, limit)
        return self.conn.execute(sql, params).fetchall()

    def set_status(self, item_id: int, status: str) -> None:
        self.conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))
        self.conn.commit()

    def get_item(self, item_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    def set_full_text(self, item_id: int, text: str) -> None:
        self.conn.execute("UPDATE items SET full_text = ? WHERE id = ?", (text, item_id))
        self.conn.commit()

    def set_summary(self, item_id: int, summary: str) -> None:
        self.conn.execute(
            "UPDATE items SET summary = ?, summarized_at = ? WHERE id = ?",
            (summary, _now(), item_id),
        )
        self.conn.commit()

    # --- the numbered view ------------------------------------------------

    def record_view(self, item_ids: list[int]) -> None:
        """Replace the current numbered view (1-based positions)."""
        self.conn.execute("DELETE FROM view")
        self.conn.executemany(
            "INSERT INTO view (pos, item_id) VALUES (?, ?)",
            [(i, item_id) for i, item_id in enumerate(item_ids, start=1)],
        )
        self.conn.commit()

    def view_item(self, pos: int) -> sqlite3.Row | None:
        row = self.conn.execute("SELECT item_id FROM view WHERE pos = ?", (pos,)).fetchone()
        return self.get_item(row["item_id"]) if row else None

    def view_item_ids(self) -> list[int]:
        return [r["item_id"] for r in self.conn.execute("SELECT item_id FROM view ORDER BY pos")]

    def view_items(self) -> list[sqlite3.Row]:
        """Items in the current numbered view, in position order."""
        return self.conn.execute(
            "SELECT items.* FROM view JOIN items ON items.id = view.item_id "
            "ORDER BY view.pos"
        ).fetchall()
