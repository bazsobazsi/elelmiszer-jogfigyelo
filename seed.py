#!/usr/bin/env python3
"""Seed adatok importálása a Coolify konténerben futó alkalmazáshoz."""
import json, os, sys, hashlib

DB_DIR = os.environ.get("ELELMISZER_DB_DIR", "/data/db")
os.makedirs(DB_DIR, exist_ok=True)

# db.py import előtt beállítjuk a DB útvonalat
os.environ["ELELMISZER_DB_DIR"] = DB_DIR

import db

seed_path = os.path.join(os.path.dirname(__file__), "seed_data.json")
with open(seed_path) as f:
    data = json.load(f)

conn = db.get_db()

# Profilok
for p in data.get("profiles", []):
    conn.execute("""INSERT OR IGNORE INTO profiles (name, product_groups, standards, export_targets)
        VALUES (?, ?, ?, ?)""", (p.get("name"), p.get("product_groups","[]"), p.get("standards","[]"), p.get("export_targets","[]")))

# Itemek
new_items = 0
for it in data.get("items", []):
    source_id = it.get("source_id") or hashlib.md5((it["title"]+it.get("url","")).encode()).hexdigest()[:16]
    iid = conn.execute("INSERT OR IGNORE INTO items (source, source_id, title, url, raw_json) VALUES (?,?,?,?,?)",
        (it["source"], source_id, it["title"], it.get("url",""), it.get("raw_json","{}"))).lastrowid
    if iid:
        new_items += 1

# Elemzések
for a in data.get("analyses", []):
    conn.execute("""INSERT OR REPLACE INTO analyses 
        (item_id, relevant, category, product_groups, standards_affected, impact_summary, action_required, deadline)
        VALUES (?,?,?,?,?,?,?,?)""",
        (a["item_id"], a["relevant"], a.get("category",""), a.get("product_groups","[]"), a.get("standards_affected","[]"),
         a.get("impact_summary",""), a.get("action_required",""), a.get("deadline","") or ""))

conn.commit()

stats = db.get_stats()
print(f"✅ Seed kész — {stats['total_items']} item, {stats['relevant_count']} releváns")
print(f"   Dashboard: http://localhost:{os.environ.get('PORT','8768')}")