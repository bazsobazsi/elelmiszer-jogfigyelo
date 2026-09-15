#!/usr/bin/env python3
"""
Compliance Agent — AI osztályozó és hatásvizsgáló
Nem csak relevanciát dönt el, hanem compliance hatásvizsgálatot végez:
- Milyen HACCP/szabvány/kötelezettség módosul?
- Mit kell tennie az ügyfélnek? (konkrét lépések)
- Milyen határidők/döntések vannak?
- Melyik GHP útmutató érintett?
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

COMPLIANCE_DOMAIN_TOPICS = {
    "Jelölés, címkézés, tápértékjelölés": {
        "keywords": ["jelölés", "címkézés", "tápérték", "allergén", "FIC", "1169/2011", "QUID"],
        "standards": ["HACCP", "BRCGS"],
        "action": "Ellenőrizni a termékcímkéket, frissíteni a jelölési adatbázist.",
    },
    "HACCP, élelmiszerhigiénia, önellenőrzés": {
        "keywords": ["HACCP", "higiénia", "önellenőrzés", "CCP", "mikrobiológia", "852/2004"],
        "standards": ["HACCP", "ISO 22000", "BRCGS", "FSSC 22000"],
        "action": "Felülvizsgálni a HACCP dokumentációt, frissíteni a CCP-monitoring tervet.",
    },
    "Adalékanyagok, aromák, szennyezőanyagok": {
        "keywords": ["adalék", "aroma", "szennyező", "mikotoxin", "aflatoxin", "nehézfém", "migráció"],
        "standards": ["HACCP", "BRCGS", "IFS Food"],
        "action": "Ellenőrizni a beszállítói adalékanyag-deklarációkat és a szennyezőanyag-vizsgálatokat.",
    },
    "Csomagolás, élelmiszerrel érintkező anyagok (FCM)": {
        "keywords": ["csomagolóanyag", "FCM", "BPA", "biszfenol", "élelmiszerekkel érintkezés"],
        "standards": ["BRCGS", "IFS Food", "FSSC 22000"],
        "action": "Beszállítói FCM-megfelelőség ellenőrzése, nyilatkozatok bekérése.",
    },
    "Speciális: novel food, GMO, étrend-kiegészítő": {
        "keywords": ["novel food", "új élelmiszer", "GMO", "étrend-kiegészítő", "2283/2015"],
        "standards": ["HACCP", "ISO 22000"],
        "action": "Termékengedélyek és EFSA-státusz ellenőrzése.",
    },
    "Export harmadik országba": {
        "keywords": ["harmadik ország", "export", "import", "USA", "FDA", "UK", "Svájc", "szerbia"],
        "standards": ["HACCP", "BRCGS", "FSSC 22000", "ISO 22000"],
        "action": "Exportpiaci jogszabálykövetés ellenőrzése az adott ország hatósági előírásai szerint.",
    },
}


def get_compliance_impact_prompt(item, profile):
    """
    Compliance hatásvizsgálat prompt.
    Nem csak osztályoz, hanem konkrét következményeket azonosít.
    """
    return f"""Te egy élelmiszeripari compliance ügynök vagy. A feladatod, hogy egy
változás/riasztás/új szabályozás hatását elemezd az alábbi ügyfél profiljára.

Ügyfél: {profile.get('name', 'Ismeretlen')}
Termékcsoportok: {json.loads(profile.get('product_groups', '[]')) if isinstance(profile.get('product_groups'), str) else profile.get('product_groups', [])}
Tanúsítványok: {json.loads(profile.get('standards', '[]')) if isinstance(profile.get('standards'), str) else profile.get('standards', [])}
Exportcélok: {json.loads(profile.get('export_targets', '[]')) if isinstance(profile.get('export_targets'), str) else profile.get('export_targets', [])}

Bejövő változás:
Forrás: {item['source']}
Cím: {item['title']}
Tartalom: {item.get('raw_json', '')[:1500]}

Elemezd:
1. Compliance relevancia (0/1)
2. Kategória: jovahagyas / modositas / riasztas / iranymutatas / GMP_utmutato / export
3. Érintett termékcsoportok (pontosan melyikek a profilból)
4. Érintett szabványok és HACCP eljárások
5. Konkrét teendő: mit kell módosítani a HACCP/dokumentáció/ellenőrzés/termék területen?
6. Határidő (ha van)
7. Melyik GHP útmutató érintett?

Válasz JSON:
{{"relevant": 0|1, "category": "...", "product_groups": [...], "standards": [...], "action_required": "...", "deadline": null vagy "...", "ghp_guide": null vagy "..."}}
"""


def run():
    """Osztályozza az összes elemzetlen itemet a compliance prompt segítségével"""
    items = db.get_unanalysed()
    profiles = db.get_active_profiles()

    if not items:
        print("✅ Nincs feldolgozatlan item")
        return

    print(f"⏳ {len(items)} feldolgozatlan item")
    print(f"👤 {len(profiles)} aktív profil")
    print()
    print("Az alábbi promptokat kell elküldeni az LLM-nek és az eredményt")
    print("db.add_analysis()-el tárolni.")
    print("=" * 50)
    for item in items:
        print(f"\n#{item['id']} [{item['source']}] {item['title'][:60]}")
        profile = profiles[0] if profiles else {"name": "Alapértelmezett"}
        prompt = get_compliance_impact_prompt(item, profile)
        print(f"  Prompt hossza: {len(prompt)} karakter")


if __name__ == "__main__":
    run()