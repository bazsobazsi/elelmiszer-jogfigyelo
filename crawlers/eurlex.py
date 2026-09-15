#!/usr/bin/env python3
"""
EUR-Lex figyelő — élelmiszerbiztonsági jogszabályok
Adatot a cron job promptja biztosít (web_extract-ból).
A script a kapott adatot dolgozza fel: dedup + DB tárolás.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db


def parse_eurlex_page(html):
    """
    EUR-Lex keresési eredményoldal feldolgozása.
    Kinyeri a találati listát: cím, CELEX, dátum, URL.
    """
    items = []

    # Minden találat egy ## [Cím](url) formában jelenik meg
    # A minta: ## [Title](https://eur-lex.europa.eu/legal-content/AUTO/?uri=CELEX:...)
    pattern = r'## \[(.*?)\]\(https://eur-lex.europa.eu/legal-content/AUTO/\?uri=CELEX:([^&]+)'
    matches = re.findall(pattern, html)
    for title, celex in matches:
        # Dátum keresése: "Date of document: DD/MM/YYYY"
        date_match = re.search(rf'CELEX number:\s*{re.escape(celex)}.*?Date of document:\s*(\d{{2}}/\d{{2}}/\d{{4}})', html, re.DOTALL)
        date_str = date_match.group(1) if date_match else ""
        # Átalakítás ISO formátumra
        if date_str:
            parts = date_str.split("/")
            date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"

        items.append({
            "title": title.strip(),
            "celex": celex.strip(),
            "date": date_str,
            "url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
        })

    return items


def run():
    """
    Adatot a cron job biztosít.
    Használat: python3 crawlers/eurlex.py 'URL-ek listája soronként'
    VAGY: web_extract által adott szöveget stdin-ről olvasva
    """
    # Stdin-ről olvasás (cron job pipel)
    html = sys.stdin.read() if not sys.stdin.isatty() else ""

    if not html.strip():
        # Ha nincs stdin adat, akkor prompt generálás a cron job-nak
        print("--- EUR-Lex figyelő — CRON PROMPT ---")
        print("""
1. Futtasd: web_extract(urls=["https://eur-lex.europa.eu/search.html?lang=hu&DTS_DOM=EURLEX&type=advanced&SUBDOM_INIT=LEGISLATION&DTS_SUBDOM=LEGISLATION&DC_CODED=13&sort=DD"])
2. A kapott HTML-t add át: python3 crawlers/eurlex.py
3. A kimenet: új item-ek listája, amiket az AI összefoglalhat
""")
        return

    items = parse_eurlex_page(html)
    new_count = 0

    for item in items:
        if not item["title"]:
            continue
        source_id = f"celex_{item['celex']}"

        item_id = db.add_item(
            source="eurlex",
            source_id=source_id,
            title=item["title"][:500],
            url=item.get("url", ""),
            published_at=item.get("date", ""),
            raw_json=json.dumps(item, ensure_ascii=False),
        )
        if item_id:
            new_count += 1
            print(f"🔍 EUR-Lex: {item['title'][:80]}")

    db.set_crawl_state("eurlex", item["celex"] if items else "")
    print(f"✅ EUR-Lex: {new_count} új item ({len(items)} találatból)")


if __name__ == "__main__":
    run()