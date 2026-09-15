#!/usr/bin/env python3
"""
EU Guidance dokumentum figyelő — DG SANTE guidance platform
Új/updated EU iránymutatások (guidance documents) az élelmiszerhigiénia területén.
"""
import hashlib
import json
import os
import re
import db

EU_GUIDANCE_URL = "https://food.ec.europa.eu/food-safety/biological-safety/food-hygiene/guidance-platform_en"


def run():
    """
    Adatot a cron job biztosít web_extract-ből.
    Használat: echo 'HTML...' | python3 crawlers/eu_guidance.py
    """
    html = sys.stdin.read() if not sys.stdin.isatty() else ""

    if not html.strip():
        print("--- EU Guidance figyelő — CRON PROMPT ---")
        print(f"""
1. web_extract(urls=["{EU_GUIDANCE_URL}"])
2. Add át a HTML-t: python3 crawlers/eu_guidance.py
3. A script kinyeri az új guidancedokumentumokat
""")
        return

    # Guidance dokumentumok kinyerése a HTML-ből
    # PDF linkek keresése (guidance dokumentumok)
    pdf_links = re.findall(r'href="([^"]+\.pdf)"[^>]*>([^<]*)', html)
    doc_links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', html)

    docs = []
    seen = set()
    for url, title in pdf_links + doc_links:
        title_clean = title.strip()
        if not title_clean or len(title_clean) < 5:
            continue
        if not any(kw in url.lower() for kw in ['.pdf', 'guidance', 'hygiene', 'higinia', 'notice']):
            continue
        dedup = title_clean + url
        if dedup in seen:
            continue
        seen.add(dedup)
        docs.append({"title": title_clean, "url": url if url.startswith("http") else f"https://food.ec.europa.eu{url}"})

    new_count = 0
    for doc in docs:
        source_id = hashlib.md5(doc["url"].encode()).hexdigest()[:16]
        iid = db.add_item(source="eu_guidance", source_id=f"eu_guidance_{source_id}",
                          title=f"[EU Guidance] {doc['title'][:200]}",
                          url=doc["url"],
                          raw_json=json.dumps(doc, ensure_ascii=False))
        if iid:
            new_count += 1
            if new_count <= 5:
                print(f"📋 EU Guidance: {doc['title'][:70]}")

    print(f"✅ EU Guidance: {new_count} új dokumentum")


if __name__ == "__main__":
    run()