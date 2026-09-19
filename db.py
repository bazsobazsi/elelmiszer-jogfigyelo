#!/usr/bin/env python3
"""
Adatbázis séma és helperek az élelmiszer-jogfigyelő rendszerhez.
SQLite, multi-tenant profilokkal.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.environ.get("ELELMISZER_DB_DIR", os.path.expanduser("~/.elelmiszer_jogfigyelo"))
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

CREATE TABLE IF NOT EXISTS email_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    smtp_host TEXT DEFAULT '',
    smtp_port INTEGER DEFAULT 587,
    smtp_user TEXT DEFAULT '',
    smtp_pass TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    to_email TEXT DEFAULT '',
    cc_email TEXT DEFAULT '',
    product_filters TEXT DEFAULT '["húskészítmény","tejtermék","pékáru"]',
    enabled INTEGER DEFAULT 0,
    send_time TEXT DEFAULT '08:00'
);

CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT DEFAULT (datetime('now')),
    recipients TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    item_count INTEGER DEFAULT 0,
    item_ids TEXT DEFAULT '[]',
    status TEXT DEFAULT 'ok',
    error TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT DEFAULT '',
    subscribed_at TEXT DEFAULT (datetime('now')),
    active INTEGER DEFAULT 1
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


def get_email_config():
    conn = get_db()
    row = conn.execute("SELECT * FROM email_config WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else {}


def save_email_config(host, port, user, passw, from_email, to_email, cc_email, filters, enabled, send_time="08:00"):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO email_config (id, smtp_host, smtp_port, smtp_user, smtp_pass, from_email, to_email, cc_email, product_filters, enabled, send_time) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (host, port, user, passw, from_email, to_email, cc_email, json.dumps(filters), 1 if enabled else 0, send_time),
    )
    conn.commit()
    conn.close()


def get_unnotified_relevant():
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.title, i.url, a.category, a.impact_summary, a.action_required, a.deadline, a.standards_affected, a.product_groups
           FROM items i
           JOIN analyses a ON i.id = a.item_id
           WHERE a.relevant = 1
             AND i.id NOT IN (SELECT item_id FROM notifications WHERE profile_id = 1)
           ORDER BY i.fetched_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified_batch(item_ids, profile_id=1):
    conn = get_db()
    for iid in item_ids:
        conn.execute("INSERT OR IGNORE INTO notifications (profile_id, item_id) VALUES (?, ?)", (profile_id, iid))
    conn.commit()
    conn.close()


def get_filters():
    conn = get_db()
    try:
        sources = [r["source"] for r in conn.execute("SELECT DISTINCT source FROM items ORDER BY source")]
        categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM analyses ORDER BY category") if r["category"]]
        return {"sources": sources, "categories": categories}
    except Exception:
        return {"sources": [], "categories": []}
    finally:
        conn.close()



def add_send_log(recipients, subject, item_count, item_ids, status='ok', error=''):
    conn = get_db()
    conn.execute(
        "INSERT INTO send_log (recipients, subject, item_count, item_ids, status, error) VALUES (?, ?, ?, ?, ?, ?)",
        (recipients, subject, item_count, json.dumps(item_ids), status, error),
    )
    conn.commit()
    conn.close()


def get_send_log(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM send_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unnotified_items():
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.source, i.title, i.url, a.category, a.impact_summary, a.action_required, a.deadline
           FROM items i
           JOIN analyses a ON i.id = a.item_id
           WHERE a.relevant = 1
             AND i.id NOT IN (SELECT item_id FROM notifications WHERE profile_id = 1)
           ORDER BY i.fetched_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified_raw(item_ids):
    conn = get_db()
    for iid in item_ids:
        conn.execute("INSERT OR IGNORE INTO notifications (profile_id, item_id) VALUES (1, ?)", (iid,))
    conn.commit()
    conn.close()


def simple_classify_item(item_id, title, source, raw_json=""):
    """
    Egyszerű szabályalapú klasszifikáció — nem kell LLM hozzá.
    Keywords matching a profil termékcsoportjai és szabványai alapján.
    """
    conn = get_db()
    try:
        text = (title + " " + (raw_json or "")).lower()
        source = (source or "").lower()
        
        # Forrás alapú kategória
        cat_map = {
            "nebih": "jogszabaly",
            "kozlony": "jogszabaly_modositas",
            "nak_ghp": "GMP_utmutato",
            "eurlex": "jogszabaly",
            "rasff": "riasztas",
            "eu_guidance": "iranymutatas",
        }
        category = "egyeb"
        for key, val in cat_map.items():
            if key in source:
                category = val
                break
        
        # Relevancia: profil termékcsoportok alapján
        profiles = conn.execute("SELECT id, product_groups, standards FROM profiles WHERE active = 1").fetchall()
        relevant = 0
        product_groups = []
        affected_standards = []
        action = ""
        
        product_keywords = {
            "húskészítmény": ["hús", "húskészítmény", "baromfi", "sertés", "marha", "nyúl", "vad", "húsfeldolgozás", "hentes"],
            "tejtermék": ["tej", "tejtermék", "sajt", "joghurt", "vaj", "tejipar", "laktóz"],
            "pékáru": ["pékáru", "kenyér", "pék", "sütőipar", "liszt", "gabona", "búza", "glutén"],
        }
        
        for p in profiles:
            groups = json.loads(p.get("product_groups", "[]")) if isinstance(p.get("product_groups"), str) else p.get("product_groups", [])
            for g in groups:
                kws = product_keywords.get(g, [g])
                for kw in kws:
                    if kw in text:
                        relevant = 1
                        if g not in product_groups:
                            product_groups.append(g)
                        break
        
        # Szabvány érintettség
        std_keywords = {
            "HACCP": ["haccp", "ccp", "önellenőrzés", "higiénia", "mikrobiológia"],
            "BRCGS": ["brc", "brcgs", "audit", "tanúsítvány"],
            "ISO 22000": ["iso 22000", "élelmiszerbiztonság", "fsms"],
            "FSSC 22000": ["fssc", "fssc 22000"],
            "IFS Food": ["ifs", "ifs food"],
        }
        for std, kws in std_keywords.items():
            for kw in kws:
                if kw in text:
                    affected_standards.append(std)
                    break
        
        # Teendő kategória szerint
        if category == "riasztás":
            action = "Ellenőrizni az érintett terméktételt, visszahívási terv aktiválása."
        elif category == "jogszabály_módosítás":
            action = "Jogszabályváltozás beépítése a HACCP dokumentációba."
        elif category == "GMP_útmutató":
            action = "GMP útmutató alapján felülvizsgálni a gyártási eljárásokat."
        elif category == "export":
            action = "Exportpiaci követelmények ellenőrzése, dokumentáció frissítése."
        
        # Impact summary
        impact_parts = []
        if product_groups:
            impact_parts.append(f"Érintett termékcsoport: {', '.join(product_groups)}")
        if affected_standards:
            impact_parts.append(f"Érintett szabvány: {', '.join(affected_standards)}")
        impact_summary = " — ".join(impact_parts) if impact_parts else ""
        
        conn.execute(
            """INSERT OR REPLACE INTO analyses (item_id, relevant, category, product_groups, standards_affected, impact_summary, action_required)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (item_id, relevant, category,
             json.dumps(product_groups, ensure_ascii=False),
             json.dumps(affected_standards, ensure_ascii=False),
             impact_summary, action),
        )
        conn.commit()
        return (relevant, category, product_groups)
    except Exception as e:
        print(f"⚠️  Classify error item {item_id}: {e}")
        return (0, "error", [])
    finally:
        conn.close()


def classify_all():
    """Minden elemzetlen item klasszifikációja"""
    conn = get_db()
    items = conn.execute(
        "SELECT i.id, i.source, i.title, i.raw_json FROM items i LEFT JOIN analyses a ON i.id = a.item_id WHERE a.id IS NULL"
    ).fetchall()
    conn.close()
    if not items:
        return 0
    count = 0
    for it in items:
        simple_classify_item(it["id"], it["title"], it["source"], it.get("raw_json", ""))
        count += 1
    return count


def get_subscribers():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, email, name, subscribed_at, active FROM subscribers WHERE active = 1 ORDER BY subscribed_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_subscriber(email, name=""):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (email, name) VALUES (?, ?)",
            (email.strip().lower(), name.strip()),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM subscribers WHERE email = ?", (email.strip().lower(),)).fetchone()
        return (True, row["id"]) if row else (False, None)
    except Exception as e:
        return (False, str(e))
    finally:
        conn.close()


def remove_subscriber(email):
    conn = get_db()
    conn.execute(
        "UPDATE subscribers SET active = 0 WHERE email = ?",
        (email.strip().lower(),),
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
    try:
        row = conn.execute(
            "SELECT COUNT(*) as total_items FROM items"
        ).fetchone() or {"total_items": 0}
        relevant = conn.execute(
            "SELECT COUNT(*) as c FROM analyses WHERE relevant = 1"
        ).fetchone() or {"c": 0}
        sources = conn.execute(
            "SELECT COUNT(DISTINCT source) as c FROM items"
        ).fetchone() or {"c": 0}
        return {
            "total_items": row["total_items"],
            "relevant_count": relevant["c"],
            "sources": sources["c"],
        }
    except Exception as e:
        return {"total_items": 0, "relevant_count": 0, "sources": 0, "error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()