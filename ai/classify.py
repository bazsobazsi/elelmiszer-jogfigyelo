#!/usr/bin/env python3
"""
Osztályozó modul — eldönti, hogy egy item releváns-e élelmiszeripari
minőségbiztosítási szempontból, és kategorizálja.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db


def classify_item(item, profiles=None):
    """
    AI osztályozás: relevancia + kategória + érintett termékcsoportok + szabványok
    Ezt a cron job fogja meghívni LLM-mel; itt a strukturált prompt sablon.
    """
    if profiles is None:
        profiles = db.get_active_profiles()

    # A visszatérési érték egy prompt sablon, amit a cron job LLM-hívásban használ
    prompt = f"""Te egy élelmiszeripari minőségbiztosítási szakértő vagy.
Elemezd a következő bejegyzést:

Forrás: {item['source']}
Cím: {item['title']}
Megjelenés: {item.get('published_at', 'ismeretlen')}
Tartalom: {item.get('raw_json', '')[:2000]}

Profilok:
{json.dumps([{
    'name': p['name'],
    'product_groups': json.loads(p['product_groups']) if isinstance(p['product_groups'], str) else p['product_groups'],
    'standards': json.loads(p['standards']) if isinstance(p['standards'], str) else p['standards'],
    'keywords': p.get('keywords', '')
} for p in profiles], ensure_ascii=False, indent=2)}

Döntsd el:
1. Releváns-e élelmiszeripari minőségbiztosítási szempontból? (0/1)
2. Kategória: "jogszabaly" / "riasztas" / "szabvany" / "egyeb"
3. Érintett termékcsoportok: [lista a profilokból, ha releváns]
4. Érintett szabványok: [BRCGS/IFS/FSSC 22000/ISO 22000/HACCP — ha köthető]

Válasz CSAK JSON formátumban:
{{"relevant": 0|1, "category": "...", "product_groups": [...], "standards": [...]}}
"""
    return prompt


def classify_from_text(text, profiles):
    """
    Szöveges elemzés promptja (PDF-ekhez, hosszabb tartalomhoz).
    """
    profiles_json = json.dumps([{
        'name': p['name'],
        'product_groups': json.loads(p['product_groups']) if isinstance(p['product_groups'], str) else p['product_groups'],
        'standards': json.loads(p['standards']) if isinstance(p['standards'], str) else p['standards'],
    } for p in profiles], ensure_ascii=False, indent=2)

    return f"""Élelmiszeripari minőségbiztosítási szakértő vagy.
Elemezd a következő szöveget (PDF tartalom):

{text[:3000]}

Profilok: {profiles_json}

Feladatok:
1. Van-e élelmiszeripari minőségbiztosítási relevanciája? (0/1)
2. Ha igen, kategória: jogszabaly / riasztas / szabvany / egyeb
3. Érintett termékcsoportok: []
4. Érintett szabványok: []
5. Van-e határidő a bevezetésre? (pl. 2026. december 31.)

Válasz JSON: {{"relevant": 0|1, "category": "...", "product_groups": [...], "standards": [...], "deadline": null}}
"""


def parse_classification(llm_response):
    """
    Feldolgozza az LLM válaszát JSON formátumban.
    """
    try:
        # JSON kinyerése a szövegből (lehet markdown kódblokkban)
        text = llm_response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        print(f"⚠️  JSON parse hiba: {llm_response[:200]}", file=sys.stderr)
        return {"relevant": 0, "category": "egyeb", "product_groups": [], "standards": []}


def process_unanalysed(profiles=None):
    """Feldolgoz minden még nem elemzett item-et a DB-ben"""
    if profiles is None:
        profiles = db.get_active_profiles()

    items = db.get_unanalysed()
    if not items:
        print("   Nincs feldolgozatlan item")
        return

    print(f"   {len(items)} feldolgozatlan item")
    for item in items:
        prompt = classify_item(item, profiles)
        # A prompt itt készen van, a cron job fogja LLM-hez küldeni
        # Ezt a classify.py-t a cron job prompt használja
        print(f"   ⏳ {item['source']}: {item['title'][:60]}")

    return items


if __name__ == "__main__":
    items = process_unanalysed()
    if items:
        print(f"✅ {len(items)} item osztályozásra vár")