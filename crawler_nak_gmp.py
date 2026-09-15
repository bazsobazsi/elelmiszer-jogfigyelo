#!/usr/bin/env python3
"""
NAK/Magyar GMP-GHP útmutató figyelő
Jó Higiéniai Gyakorlat (GHP) útmutatók az elelmiszerlanc.kormany.hu-ról.
"""
import hashlib
import json
import os
import re
import db

NAK_GHP_URL = "https://elelmiszerlanc.kormany.hu/jo-higieniai-gyakorlat-utmutatok"

SECTOR_MAP = {
    "hús": "húskészítmény", "baromfi": "húskészítmény", "sertés": "húskészítmény",
    "marha": "húskészítmény", "vendéglátás": "vendéglátás", "étkeztetés": "vendéglátás",
    "tej": "tejtermék", "sütő": "pékáru", "cukor": "cukoripar",
    "konzerv": "konzervipar", "gyorsfagyasztott": "gyorsfagyasztott",
    "hal": "halászati termék", "kiskereskedelmi": "kiskereskedelem",
    "kistermelői": "kistermelő", "alkoholmentes": "italgyártás",
    "jégkrém": "jégkrém", "száraztészta": "száraztészta", "szeszesital": "szeszesital",
    "tojás": "tojástermék", "hűtött": "hűtött élelmiszer", "cukoripar": "cukoripar",
    "malomipar": "malomipar", "söripar": "söripar", "édesipar": "édesipar",
    "növényolaj": "növényolaj", "szikvíz": "üdítőital",
}


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

    # Markdown formátum: [Title](url.pdf)
    # web_extract ezt adja vissza
    pdf_pattern = re.findall(
        r'\[([^\]]+)\]\(([^)]+\.pdf)\)', html
    )
    guides = []
    seen = set()
    for title_clean, full_url in pdf_pattern:
        title_clean = title_clean.replace("**", "").strip()
        # Szűrés: csak útmutatók
        if not title_clean or "útm" not in title_clean.lower()[:5]:
            if not any(k in title_clean.lower() for k in ["higiénia", "ghp", "gmp", "gyakorlat"]):
                continue

        if not full_url.startswith("http"):
            full_url = f"https://elelmiszerlanc.kormany.hu/{full_url.lstrip('/')}"
        dedup = title_clean + full_url
        if dedup in seen:
            continue
        seen.add(dedup)

        # Szektor detektálás
        sectors = []
        for keyword, sector in SECTOR_MAP.items():
            if keyword in title_clean.lower():
                sectors.append(sector)
        if not sectors:
            sectors.append("általános élelmiszeripar")

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