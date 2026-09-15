#!/usr/bin/env python3
"""
RASFF figyelő — EU Rapid Alert System for Food and Feed
Adatot a cron job biztosít (web_extract/web_search által).
"""
import json
import os
import re
import db


def parse_rasff_page(html):
    """
    RASFF keresési oldal feldolgozása (minimalista parser).
    A RASFF Window JS-ben renderelődik, így a html-ből korlátozottan
    tudunk adatot kinyerni. Alternatíva: web_search + RASFF hírek.
    """
    # Egyszerű: keressünk notification referenciákat
    refs = re.findall(r'(\d{4}\.\s*\d+)', html)
    items = []
    for ref in refs[:50]:
        items.append({
            "reference": ref.strip(),
            "subject": "",
            "url": f"https://webgate.ec.europa.eu/rasff-window/screen/notification/{ref.replace(' ', '')}",
            "date": "",
        })
    return items


def run():
    """
    Használat:
      python3 crawlers/rasff.py          # prompt generálás
      echo "HTML..." | python3 crawlers/rasff.py  # feldolgozás
    """
    html = sys.stdin.read() if not sys.stdin.isatty() else ""

    if not html.strip():
        print("--- RASFF figyelő — CRON PROMPT ---")
        print("""
1. web_extract: https://webgate.ec.europa.eu/rasff-window/screen/search
   (a RASFF JS-ben renderel, ezért inkább web_search-t használj)
2. web_search: "RASFF alert 2026 food safety recall"
   vagy: "site:ec.europa.eu RASFF 2026 notification"
3. A találatokat add át: python3 crawlers/rasff.py
""")
        return

    items = parse_rasff_page(html)
    if not items:
        # Nincs használható adat a HTML-ből
        print("⚠️  RASFF HTML nem tartalmaz notification adatokat")
        print("   → Használj web_search-t RASFF témában a cron job prompt részeként")
        return

    new_count = 0
    for item in items:
        source_id = f"rasff_{item['reference'].replace(' ', '_')}"
        item_id = db.add_item(
            source="rasff",
            source_id=source_id,
            title=f"RASFF riasztás: {item['reference']}",
            url=item.get("url", ""),
            published_at=item.get("date"),
            raw_json=json.dumps(item, ensure_ascii=False),
        )
        if item_id:
            new_count += 1
            print(f"🔴 RASFF: {item['reference']}")

    print(f"✅ RASFF: {new_count} új riasztás")


if __name__ == "__main__":
    run()