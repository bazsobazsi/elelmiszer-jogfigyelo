#!/usr/bin/env python3
"""
Adatbázis séma és helperek az élelmiszer-jogfigyelő rendszerhez.
SQLite, multi-tenant profilokkal.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.path.expanduser("~/.elelmiszer_jogfigyelo")
DB_PATH = os.path.join(DB_DIR, "state.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT UNIQUE,
    title TEXT NOT NULL,
    url TEXT,
    published_at TEXT,
    raw_json TEXT,
    fetched_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    relevant INTEGER DEFAULT 0,
    category TEXT,
    product_groups TEXT,
    impact_summary TEXT,
    action_required TEXT,
    deadline TEXT,
    standards_affected TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    product_groups TEXT NOT NULL DEFAULT '[]',
    standards TEXT NOT NULL DEFAULT '[]',
    keywords TEXT DEFAULT '',
    export_targets TEXT DEFAULT '[]',
    notification_channel TEXT DEFAULT 'telegram',
    notification_target TEXT DEFAULT '',
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    item_id INTEGER,
    sent_at TEXT DEFAULT (datetime('now')),
    UNIQUE(profile_id, item_id)
);

CREATE TABLE IF NOT EXISTS crawl_state (
    source TEXT PRIMARY KEY,
    last_cursor TEXT,
    last_run TEXT
);
"""


def get_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    # Alap profil létrehozása (demo)
    profiles = conn.execute("SELECT COUNT(*) as c FROM profiles").fetchone()
    if profiles["c"] == 0:
        conn.execute(
            "INSERT INTO profiles (name, product_groups, standards, keywords, export_targets, notification_channel) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Első ügyfél",
                json.dumps(["húskészítmény", "tejtermék", "pékáru"]),
                json.dumps(["BRCGS", "HACCP", "ISO 22000"]),
                "allergén, mikrobiológiai, Salmonella, Listeria",
                json.dumps(["EU", "UK", "Svájc"]),
                "telegram",
            ),
        )
    conn.commit()
    conn.close()
    print(f"✅ DB inicializálva: {DB_PATH}")
    print(f"   Profilok: {profiles['c']} (1 alapértelmezett létrehozva)")


def add_item(source, source_id, title, url=None, published_at=None, raw_json=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO items (source, source_id, title, url, published_at, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
            (source, source_id, title, url, published_at, raw_json),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM items WHERE source_id = ?", (source_id,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_unanalysed():
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.source, i.title, i.url, i.published_at, i.raw_json
           FROM items i
           LEFT JOIN analyses a ON i.id = a.item_id
           WHERE a.id IS NULL
           ORDER BY i.fetched_at ASC"""
    ).fetchall()
    conn.close()
    return rows


def add_analysis(item_id, relevant, category, product_groups, impact_summary,
                 action_required, deadline, standards_affected):
    conn = get_db()
    conn.execute(
        """INSERT INTO analyses (item_id, relevant, category, product_groups,
                                 impact_summary, action_required, deadline, standards_affected)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (item_id, int(relevant), category,
         json.dumps(product_groups, ensure_ascii=False) if isinstance(product_groups, list) else product_groups,
         impact_summary, action_required, deadline,
         json.dumps(standards_affected, ensure_ascii=False) if isinstance(standards_affected, list) else standards_affected),
    )
    conn.commit()
    conn.close()


def get_crawl_state(source):
    conn = get_db()
    row = conn.execute(
        "SELECT last_cursor, last_run FROM crawl_state WHERE source = ?", (source,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {"last_cursor": None, "last_run": None}


def set_crawl_state(source, cursor):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO crawl_state (source, last_cursor, last_run) VALUES (?, ?, datetime('now'))",
        (source, cursor),
    )
    conn.commit()
    conn.close()


def get_active_profiles():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, product_groups, standards, keywords, notification_channel, notification_target FROM profiles WHERE active = 1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified(profile_id, item_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO notifications (profile_id, item_id) VALUES (?, ?)",
        (profile_id, item_id),
    )
    conn.commit()
    conn.close()


def get_daily_digest(date_str=None):
    """Releváns, még nem küldött item-ek egy adott napra"""
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.source, i.title, i.url, i.published_at,
                  a.category, a.impact_summary, a.action_required, a.deadline,
                  a.standards_affected, a.product_groups
           FROM items i
           JOIN analyses a ON i.id = a.item_id
           WHERE a.relevant = 1
             AND date(i.fetched_at) = ?
           ORDER BY i.published_at DESC""",
        (date_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_items(week_ago):
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.source, i.title, i.url, i.published_at,
                  a.category, a.impact_summary, a.action_required, a.deadline,
                  a.standards_affected, a.product_groups
           FROM items i
           JOIN analyses a ON i.id = a.item_id
           WHERE a.relevant = 1
             AND date(i.fetched_at) >= ?
           ORDER BY i.published_at DESC""",
        (week_ago,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_items_with_analysis(limit=50, offset=0):
    conn = get_db()
    rows = conn.execute(
        """SELECT i.*, COALESCE(a.relevant, 0) as relevant, a.category, a.impact_summary,
                  a.action_required, a.deadline, a.standards_affected, a.product_groups,
                  CASE WHEN a.id IS NULL THEN 0 ELSE 1 END as analysed
           FROM items i
           LEFT JOIN analyses a ON i.id = a.item_id
           ORDER BY i.fetched_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_db()
    row = conn.execute(
        """SELECT
            COUNT(*) as total_items,
            SUM(CASE WHEN i.fetched_at >= date('now') THEN 1 ELSE 0 END) as today_items,
            (SELECT COUNT(*) FROM items WHERE fetched_at >= date('now')) as today_total
           FROM items i"""
    ).fetchone()
    relevant = conn.execute(
        "SELECT COUNT(*) as c FROM analyses a JOIN items i ON a.item_id = i.id WHERE a.relevant = 1 AND date(i.fetched_at) = date('now')"
    ).fetchone()
    sources = conn.execute(
        "SELECT COUNT(DISTINCT source) as c FROM items"
    ).fetchone()
    conn.close()
    return {
        "total_items": row["today_total"] if row else 0,
        "relevant_count": relevant["c"] if relevant else 0,
        "sources": sources["c"] if sources else 0,
    }


if __name__ == "__main__":
    init_db()