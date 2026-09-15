#!/usr/bin/env python3
"""
Szabványfrissítés figyelő — BRCGS, IFS, FSSC 22000, ISO 22000
Hetente egyszer fut, web_search + web_extract segítségével.
"""
import hashlib
import json
import os
import re
import db

# Szabványok és forrásaik
STANDARDS = [
    {
        "name": "BRCGS",
        "current_issue": "Issue 9",
        "keywords": ["BRCGS", "new issue", "standard update", "food safety"],
        "url": "https://www.brcgs.com",
    },
    {
        "name": "IFS Food",
        "current_issue": "Version 8",
        "keywords": ["IFS Food", "IFS standard", "update"],
        "url": "https://www.ifs-certification.com",
    },
    {
        "name": "FSSC 22000",
        "current_issue": "Version 6",
        "keywords": ["FSSC 22000", "scheme update", "new version"],
        "url": "https://www.fssc.com",
    },
    {
        "name": "ISO 22000",
        "current_issue": "ISO 22000:2018",
        "keywords": ["ISO 22000", "revision", "food safety management"],
        "url": "https://www.iso.org",
    },
]


def check_standard(standard):
    """
    Web_search segítségével ellenőrzi, van-e hír a szabvány frissítéséről.
    Ezt a cron job fogja meghívni a search eszközzel.
    """
    # Ezt a függvényt a cron job promptban hívjuk meg,
    # mert a search eszköz nem elérhető a scriptből
    return standard


def run():
    """Fő belépési pont — heti cronból"""
    # A cron job prompt része lesz a web_search hívás;
    # itt csak placeholder a struktúrához
    state = db.get_crawl_state("szabvany")
    print(f"✅ Szabványfigyelő: {len(STANDARDS)} szabvány regisztrálva")
    print(f"   Utolsó ellenőrzés: {state.get('last_run', 'még nem futott')}")
    for s in STANDARDS:
        print(f"   - {s['name']} ({s['current_issue']})")


if __name__ == "__main__":
    run()