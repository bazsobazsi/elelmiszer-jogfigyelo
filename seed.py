#!/usr/bin/env python3
"""Seed adatok importálása — source_id alapú ID mapping."""
import json, os, sys, hashlib

# DB útvonal beállítása
DB_DIR = os.environ.get("ELELMISZER_DB_DIR", os.path.expanduser("~/.elelmiszer_jogfigyelo"))
os.environ["ELELMISZER_DB_DIR"] = DB_DIR
import db

# DB inicializálása (táblák létrehozása)
db.init_db()

seed_path = os.path.join(os.path.dirname(__file__), "seed_data.json")
with open(seed_path) as f:
    data = json.load(f)

conn = db.get_db()

# Profilok
for p in data.get("profiles", []):
    conn.execute("INSERT OR IGNORE INTO profiles (name, product_groups, standards, export_targets) VALUES (?, ?, ?, ?)",
                 (p.get("name"), p.get("product_groups","[]"), p.get("standards","[]"), p.get("export_targets","[]")))

# Itemek + ID mapping (source_id → new item_id)
id_map = {}
new_count = 0
for it in data.get("items", []):
    source_id = it.get("source_id") or hashlib.md5((it["title"]+it.get("url","")).encode()).hexdigest()[:16]
    # Meglévő keresése
    existing = conn.execute("SELECT id FROM items WHERE source_id = ?", (source_id,)).fetchone()
    if existing:
        new_id = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO items (source, source_id, title, url, published_at, raw_json) VALUES (?,?,?,?,?,?)",
            (it["source"], source_id, it["title"], it.get("url",""), it.get("published_at",""), it.get("raw_json","{}"))
        )
        new_id = cur.lastrowid
        new_count += 1
    id_map[it["id"]] = new_id

# Analyses — a seed_data.json-ban lévő item_id → új item_id
ana_count = 0
for a in data.get("analyses", []):
    old_iid = a["item_id"]
    new_iid = id_map.get(old_iid)
    if not new_iid:
        continue
    conn.execute(
        "INSERT OR REPLACE INTO analyses (item_id, relevant, category, product_groups, standards_affected, impact_summary, action_required, deadline) VALUES (?,?,?,?,?,?,?,?)",
        (new_iid, a["relevant"], a.get("category",""), a.get("product_groups","[]"), a.get("standards_affected","[]"),
         a.get("impact_summary",""), a.get("action_required",""), a.get("deadline","") or "")
    )
    ana_count += 1

conn.commit()
conn.close()

stats = db.get_stats()
print(f"✅ Seed kész — {stats['total_items']} item ({new_count} új), {ana_count} analysis, {stats['relevant_count']} releváns")