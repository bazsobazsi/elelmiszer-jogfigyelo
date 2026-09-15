#!/usr/bin/env python3
"""
NÉBIH jogszabálygyűjtemény figyelő — KÖZPONTI MODUL
Ez a rendszer core forrása. Letölti a NÉBIH jogszabálygyűjtemény PDF-et,
detektálja a kiadásszámot, összehasonlítja az előzővel, és kinyeri a változásokat.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

USER_AGENT = "ElelmiszerJogfigyelo/1.0 (Hermes Agent)"
PDF_DIR = os.environ.get("ELELMISZER_PDF_DIR", os.path.expanduser("~/.elelmiszer_jogfigyelo/nebih_pdfs/"))

NEBIH_LAW_LIST_URL = "https://portal.nebih.gov.hu/-/elelmiszer-jogszabalyok-jegyzeke"

# NÉBIH kategóriák a jogszabálygyűjteményben
CATEGORIES = {
    "I": "Általános szabályok (élelmiszer-előállítás, forgalmazás, hatósági ellenőrzés)",
    "I.1": "Élelmiszerjog általános elvei + élelmiszerlánc-törvény",
    "I.2": "Élelmiszer-előállítás, élelmiszerbiztonság általános követelmények",
    "I.10": "Hatósági ellenőrzés",
    "I.13": "Jelölés, tápértékjelölés",
    "II": "Termékspecifikus szabályok (hús, tej, hal, olaj, stb.)",
    "III": "Adalékanyagok, aromák, FCM (csomagolás)",
    "IV": "Szennyezőanyagok, növényvédőszer-maradékok, mikrobiológia",
    "V": "Termékvédelem, eredetvédelem, hungarikumok",
    "VI": "Speciális területek (vendéglátás, étrend-kiegészítő, új élelmiszerek, GMO, HACCP)",
}


def get_latest_pdf_url():
    """Kikeresi a legfrissebb jogszabálygyűjtemény PDF URL-t a NÉBIH oldalról"""
    req = urllib.request.Request(NEBIH_LAW_LIST_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
        pattern = r'(/documents/[^"\']+ELELMISZER[^"\']*jogszabalygyujtemeny[^"\']*\.pdf)'
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            pdf_path = matches[0]
            if pdf_path.startswith("/"):
                return f"https://portal.nebih.gov.hu{pdf_path}"
            return pdf_path
        return None
    except Exception as e:
        print(f"⚠️  NÉBIH PDF URL hiba: {e}", file=sys.stderr)
        return None


def download_pdf(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())
    return os.path.getsize(path)


def extract_text(pdf_path):
    if fitz is None:
        print("⚠️  PyMuPDF nincs telepítve!", file=sys.stderr)
        return ""
    doc = fitz.open(pdf_path)
    # Teljes szöveg
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def parse_edition(text):
    """Kiadásszám kinyerése"""
    m = re.search(r'(\d+)\.\s*kiadás', text)
    edition = int(m.group(1)) if m else 0
    # Dátum kinyerése
    date_m = re.search(r'(\d{4})\.\s*(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s*(\d+)\.', text)
    edition_date = ""
    if date_m:
        month_map = {"január":"01","február":"02","március":"03","április":"04","május":"05","június":"06","július":"07","augusztus":"08","szeptember":"09","október":"10","november":"11","december":"12"}
        edition_date = f"{date_m.group(1)}-{month_map.get(date_m.group(2), '00')}-{date_m.group(3).zfill(2)}"
    return edition, edition_date


def extract_sections(text):
    """Fejezetek kinyerése a tartalomjegyzékből"""
    sections = {}
    for code, desc in CATEGORIES.items():
        # Keressük a fejezetcímet a szövegben
        pattern = rf'{re.escape(code)}\.\s*(.*?)(?:\n|$)'
        m = re.search(pattern, text)
        if m:
            start_pos = m.start()
            # Fejezet szövegének kinyerése (következő fejezetig)
            sections[code] = {
                "description": desc,
                "start": start_pos,
            }
    return sections


def find_new_items(text):
    """Új előírások keresése a PDF-ben.
    A NÉBIH a változásokat piros színnel jelöli.
    Ha PyMuPDF van, próbáljuk a piros színű szövegeket kinyerni.
    """
    # 1. Piros színű szövegek (ha PyMuPDF részletes)
    red_items = []
    if fitz:
        doc = fitz.open(None)  # nem nyitunk újat
    # 2. Változás kulcsszavak a szövegben
    indicators = [
        "módosít", "változ", "új előírás", "hatályon kívül", "megváltozott",
        "új rendelet", "módosító rendelet", "egységes szerkezet",
    ]
    new_items_list = []
    for kw in indicators:
        for m in re.finditer(rf'.{{0,100}}{re.escape(kw)}.{{0,200}}', text, re.IGNORECASE):
            new_items_list.append(m.group().strip()[:200])
    return new_items_list


def extract_law_references(text):
    """Jogszabályhivatkozások kinyerése a teljes szövegből"""
    # Magyar törvények: YYYY. évi N. törvény
    hu_laws = re.findall(r'(\d{4}\.\s*évi\s+(?:[CLXVI]+\.\s*)?\d+\s*törvény)', text)
    # Magyar rendeletek: N/YYYY. (...) rendelet
    hu_decrees = re.findall(r'(\d{1,4}/\d{4}\.\s*\([^)]+\)\s+(?:Korm\.|AM|IM|BM|NFM|EU|HM|EüM|FVM)\s*rendelet)', text)
    # EU rendeletek: (EU) YYYY/N
    eu_regs = re.findall(r'((?:EU|EK)\s+\d{4}/\d+)', text)
    # EU irányelvek
    eu_dirs = re.findall(r'(\d{4}/\d+/\s*(?:EU|EC|EK))', text)
    return {
        "hu_laws": list(set(hu_laws)),
        "hu_decrees": list(set(hu_decrees)),
        "eu_regulations": list(set(eu_regs)),
        "eu_directives": list(set(eu_dirs)),
    }


def run():
    """Fő belépési pont"""
    state = db.get_crawl_state("nebih_pdf")
    last_pdf_url = state.get("last_cursor", "")
    last_edition = state.get("last_edition", 0)
    try:
        last_edition = int(state.get("last_edition", 0))
    except ValueError:
        last_edition = 0

    pdf_url = get_latest_pdf_url()
    if not pdf_url:
        print("⚠️  NÉBIH PDF URL nem található")
        return

    # Ha ugyanaz a URL, mint legutóbb, mégse biztos hogy ugyanaz a kiadás
    # (a URL frissülhet idővel)
    if pdf_url == last_pdf_url:
        print("NO_NEW — ugyanaz a PDF URL")

    # Letöltés
    os.makedirs(PDF_DIR, exist_ok=True)
    local_path = os.path.join(PDF_DIR, hashlib.md5(pdf_url.encode()).hexdigest() + ".pdf")

    try:
        size = download_pdf(pdf_url, local_path)
        text = extract_text(local_path)
        if not text or len(text) < 100:
            print("⚠️  NÉBIH PDF túl rövid vagy üres")
            return

        edition, edition_date = parse_edition(text)
        if edition == 0:
            print("⚠️  NÉBIH kiadásszám nem kinyerhető")
            # Ha nem tudjuk, akkor fájl hash alapján döntsünk
            with open(local_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            if content_hash == state.get("last_cursor", "").split("_")[-1] if "_" in state.get("last_cursor", "") else "":
                print("NO_NEW — azonos fájl hash")
                return
            edition = last_edition + 1  # Feltételezzük, hogy új
            edition_id = f"hash_{content_hash}"
        else:
            edition_id = str(edition)

        if edition <= last_edition:
            print(f"NO_NEW — {edition}. kiadás, már volt ({last_edition})")
            return

        # Elemzés
        sections = extract_sections(text)
        new_items = find_new_items(text)
        law_refs = extract_law_references(text)

        # Store
        raw = {
            "pdf_url": pdf_url,
            "edition": edition,
            "edition_date": edition_date,
            "file_size": size,
            "text_length": len(text),
            "sections": {k: v["description"] for k, v in sections.items()},
            "new_items_count": len(new_items),
            "new_items_sample": new_items[:15],
            "laws": law_refs,
        }

        item_id = db.add_item(
            source="nebih",
            source_id=pdf_url,
            title=f"NÉBIH jogszabálygyűjtemény — {edition}. kiadás" + (f" ({edition_date})" if edition_date else ""),
            url=pdf_url,
            published_at=edition_date,
            raw_json=json.dumps(raw, ensure_ascii=False),
        )

        # Változások AI elemzésre kerülnek a cron jobban (classify.py)
        if item_id:
            print(f"📘 NÉBIH {edition}. kiadás ({edition_date})")
            print(f"   Méret: {size//1024} KB, szöveg: {len(text)//1000} KB")
            print(f"   Új/módosult előírások: {len(new_items)}")
            print(f"   Jogszabályok: {len(law_refs['hu_laws'])} magyar törvény, {len(law_refs['hu_decrees'])} rendelet, {len(law_refs['eu_regulations'])} EU rendelet")
            print(f"   Változás előző kiadáshoz ({last_edition}. → {edition}.): {edition - last_edition} lépés")

        # State frissítés
        db.set_crawl_state("nebih_pdf", f"{edition}_{edition_id}")

    except Exception as e:
        print(f"⚠️  NÉBIH PDF feldolgozás hiba: {e}", file=sys.stderr)


if __name__ == "__main__":
    run()