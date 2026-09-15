#!/usr/bin/env python3
"""
NAK/Magyar GMP-GHP útmutató figyelő
Jó Higiéniai Gyakorlat (GHP) útmutatók az élelmiszerlanc.kormany.hu-ról.
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

NAK_GHP_URL = "https://elelmiszerlanc.kormany.hu/jo-higieniai-gyakorlat-utmutatok"


def run():
    html = sys.stdin.read() if not sys.stdin.isatty() else ""

    if not html.strip():
        print("--- NAK GHP figyelő — CRON PROMPT ---")
        print(f"""
1. web_extract(urls=["{NAK_GHP_URL}"])
2. Add át: python3 crawlers/nak_gmp.py
3. Kinyeri a GMP/GHP útmutató PDF-eket és változásokat
""")
        return

    # PDF útmutatók kinyerése
    # Minta: <a href="download/.../GHP_neve.pdf">Útmutató címe</a>
    pdf_pattern = re.findall(
        r'<a\s+href="(download/[^"]+\.pdf)"[^>]*>(.*?)</a>', html, re.IGNORECASE
    )

    guides = []
    seen = set()
    for rel_url, title in pdf_pattern:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        if not title_clean or "útmutató" not in title_clean.lower():
            continue
        full_url = f"https://elelmiszerlanc.kormany.hu/{rel_url}" if rel_url.startswith("download") else rel_url
        dedup = title_clean + full_url
        if dedup in seen:
            continue
        seen.add(dedup)

        # Élelmiszeripari szektor detektálása a címből
        sectors = []
        sector_map = {
            "hús": "húskészítmény",
            "baromfi": "húskészítmény",
            "vendéglátás": "vendéglátás",
            "étkeztetés": "vendéglátás",
            "tej": "tejtermék",
            "sütő": "pékáru",
            "cukor": "cukoripar",
            "konzerv": "konzervipar",
            "gyorsfagyasztott": "gyorsfagyasztott",
            "hal": "halászati termék",
            "kiskereskedelmi": "kiskereskedelem",
        }
        for keyword, sector in sector_map.items():
            if keyword in title_clean.lower():
                sectors.append(sector)

        guides.append({
            "title": title_clean,
            "url": full_url,
            "sectors": sectors,
        })

    new_count = 0
    for guide in guides:
        source_id = hashlib.md5(guide["url"].encode()).hexdigest()[:16]
        title_full = f"[GHP] {guide['title']}"
        if guide["sectors"]:
            title_full += f" ({', '.join(guide['sectors'])})"

        iid = db.add_item(source="nak_ghp", source_id=f"nak_ghp_{source_id}",
                          title=title_full[:500], url=guide["url"],
                          raw_json=json.dumps(guide, ensure_ascii=False))
        if iid:
            new_count += 1
            if new_count <= 8:
                print(f"📕 GHP: {guide['title'][:60]} | szektor: {guide['sectors']}")

    print(f"✅ NAK GHP: {new_count} új útmutató")


if __name__ == "__main__":
    run()