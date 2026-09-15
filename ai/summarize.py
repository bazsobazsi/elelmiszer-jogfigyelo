#!/usr/bin/env python3
"""
Összefoglaló modul — magyar nyelvű B2B összefoglalók generálása
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def summarize_prompt(item, profile_name="Ügyfél"):
    """
    Prompt egyetlen item összefoglalásához.
    """
    standards = item.get("standards_affected", "")
    if isinstance(standards, str):
        try:
            standards = json.loads(standards)
        except (json.JSONDecodeError, TypeError):
            standards = [standards]

    return f"""Élelmiszeripari minőségbiztosítási szakértő vagy.
Készíts tömör, gyakorlatias összefoglalót a következő változásról, {profile_name} számára:

Forrás: {item['source']}
Cím: {item['title']}
Kategória: {item.get('category', '')}
Érintett szabványok: {standards}

Tartalom: {item.get('raw_json', '')[:2000]}

Formátum (pontosan ennyi információ, max 4 sor):
- Mi változott? (1 mondat)
- Mit kell tennie? (1 mondat, konkrét lépés)
- Határidő: (ha van, ha nincs, írd: "nincs")
- Link: {item.get('url', '')}

Válasz JSON:
{{"impact_summary": "...", "action_required": "...", "deadline": null vagy "2026-12-31"}}
"""


def weekly_digest_prompt(items, profile_name="Ügyfél"):
    """
    Heti összefoglaló prompt — kategorizálva.
    """
    items_json = json.dumps(items, ensure_ascii=False, indent=2)
    return f"""Élelmiszeripari minőségbiztosítási szakértő vagy.
Készíts heti összefoglalót {profile_name} számára az alábbi változásokból.
Csoportosítsd kategóriánként (Jogszabály / Riasztás / Szabvány).

Item-ek:
{items_json}

Formátum:
🍽️ Heti Élelmiszer-jogfigyelő — {profile_name}
⏰ {profilenév_fejléc}
🔴 JOGSZABÁLY (N db)
- cím: 1 soros összegzés

🟡 RIASZTÁS (N db)
...

🔵 SZABVÁNY (N db)
...

✅ Nincs változás: (szabványok, ahol nem volt)

Tömör, B2B minőség, felsorolás.
"""
