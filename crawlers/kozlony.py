#!/usr/bin/env python3
"""
Magyar Közlöny figyelő — élelmiszeripari domain (adaptálva a meglévő MK Figyelőből)
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

RSS_URL = "https://magyarkozlony.hu/feed"
USER_AGENT = "ElelmiszerJogfigyelo/1.0 (Hermes Agent)"
PDF_DIR = os.path.expanduser("~/.elelmiszer_jogfigyelo/pdfs/")
MAX_NEW = 2  # egyszerre max 2 számot dolgozunk fel (teljesítmény)

# Élelmiszeripari domain kulcsszavak
FOOD_KEYWORDS = [
    "élelmiszer", "élelmiszerbiztonság", "élelmiszerlánc", "élelmiszeripar",
    "NÉBIH", "élelmiszerhigiénia", "HACCP", "önellenőrzés",
    "élelmiszerkönyv", "jelölés", "címkézés", "tápértékjelölés",
    "adalékanyag", "aroma", "szennyezőanyag", "mikrobiológiai",
    "termékvisszahívás", "RASFF", "allergén", "ételmérgezés",
    "élelmiszer-megbetegedés", "higiéniai", "élelmiszer-ellenőrzés",
    "húskészítmény", "tejtermék", "pékáru", "cukrász", "húsfeldolgozó",
    "vendéglátás", "közétkeztetés", "élelmiszer-feldolgozó",
    "nyomonkövethetőség", "nyomon követhetőség", "forgalomba hozatal",
    "élelmiszer-kereskedelem", "csomagolóanyag", "élelmiszerekkel érintkezésbe",
    "élelmiszerhulladék", "állat-egészségügyi", "vágóhíd",
]

# Jogszabály-hivatkozás regex (törvény/rendelet formátumok)
LAW_REF_REGEX = re.compile(
    r"(\d{4}\.\s*évi\s+(?:[CLXVI]+\.\s*)?törvény|\d{1,4}/\d{4}\.\s*\([^)]+\)\s+(?:Korm\.|EU|EK|AM|IM|BFH|VM|FVM|KvVM|BM|NFM|NGM)?\s*(?:rendelet|határozat)|(?:EU|EK)\s+\d{4}/\d+|\d{4}/\d+/\s*EU|\d{4}/\d+/\s*EK)"
)


def fetch_rss():
    """Lekérdezi a Közlöny RSS-t"""
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = []
        for item in root.iter("item"):
            items.append(
                {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "pubDate": item.findtext("pubDate", ""),
                }
            )
        return items
    except Exception as e:
        print(f"⚠️  Közlöny RSS hiba: {e}", file=sys.stderr)
        return []


def download_pdf(url, path):
    """Letölti a PDF-et"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())


def extract_text(pdf_path):
    """PyMuPDF szövegkinyerés"""
    if fitz is None:
        return None
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def categorize(text):
    """Kulcsszavas találatok + találatszám"""
    matches = {}
    for kw in FOOD_KEYWORDS:
        count = text.lower().count(kw.lower())
        if count > 0:
            matches[kw] = count
    return matches


def find_law_refs(text):
    """Jogszabály-hivatkozások keresése"""
    return list(set(LAW_REF_REGEX.findall(text)))


def process_pdf(item):
    """Letölti + elemzi az adott szám PDF-jét"""
    if not item["link"]:
        return None
    os.makedirs(PDF_DIR, exist_ok=True)

    # PDF URL: a közlöny oldalon a letöltés link
    pdf_url = item["link"]
    # A megtekintes link helyett a letoltes végpont
    pdf_url = pdf_url.replace("/megtekintes", "/letoltes")

    local_path = os.path.join(PDF_DIR, hashlib.md5(pdf_url.encode()).hexdigest() + ".pdf")
    try:
        if not os.path.exists(local_path):
            download_pdf(pdf_url, local_path)
        text = extract_text(local_path)
        if not text:
            return None
        matches = categorize(text)
        law_refs = find_law_refs(text)
        return {
            "text_len": len(text),
            "keyword_matches": matches,
            "law_refs": law_refs,
            "relevant": len(matches) > 0,
        }
    except Exception as e:
        print(f"⚠️  PDF feldolgozás hiba ({item['title']}): {e}", file=sys.stderr)
        return None


def run():
    """Fő belépési pont — napi cronból"""
    items = fetch_rss()
    if not items:
        print("NO_NEW — RSS üres/hiba")
        return

    # Előző feldolgozás állapota
    state = db.get_crawl_state("kozlony")
    last_cursor = state["last_cursor"] or ""

    new_items = []
    for item in items:
        if item["link"] == last_cursor:
            break  # elértük a már feldolgozottat
        new_items.append(item)

    new_items = new_items[:MAX_NEW]
    if not new_items:
        print("NO_NEW")
        return

    for item in reversed(new_items):  # régebbitől újabb felé
        result = process_pdf(item)
        if not result:
            continue
        item_id = db.add_item(
            source="kozlony",
            source_id=item["link"],
            title=item["title"][:500],
            url=item["link"],
            published_at=item["pubDate"] or None,
            raw_json=json.dumps(result, ensure_ascii=False),
        )
        if item_id:
            print(f"📄 Közlöny szám: {item['title'][:60]}")
            print(f"   Releváns kulcsszavak: {list(result['keyword_matches'].keys())[:8]}")
            print(f"   Jogszabályok: {result['law_refs'][:5]}")

    # Cursor frissítése (legújabb feldolgozott link)
    if new_items:
        db.set_crawl_state("kozlony", new_items[0]["link"])

    print(f"✅ Közlöny: {len(new_items)} szám feldolgozva")


if __name__ == "__main__":
    run()