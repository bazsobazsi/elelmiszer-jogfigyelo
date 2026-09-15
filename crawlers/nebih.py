#!/usr/bin/env python3
"""
NÉBIH figyelő — jogszabálygyűjtemény PDF diff + friss hírek
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
    import fitz
except ImportError:
    fitz = None

USER_AGENT = "ElelmiszerJogfigyelo/1.0 (Hermes Agent)"
PDF_DIR = os.path.expanduser("~/.elelmiszer_jogfigyelo/nebih_pdfs/")

# A NÉBIH jogszabálygyűjtemény oldala — innen kapjuk a legfrissebb PDF linket
NEBIH_LAW_LIST_URL = "https://portal.nebih.gov.hu/-/elelmiszer-jogszabalyok-jegyzeke"
NEBIH_NEWS_URL = "https://portal.nebih.gov.hu/friss-hirek"


def get_latest_pdf_url():
    """
    Kikeresi a legfrissebb jogszabálygyűjtemény PDF URL-t a NÉBIH oldalról.
    A link általában így néz ki:
    /documents/10182/765581/132.+kiadas+ELELMISZER+jogszabalygyujtemeny.pdf
    """
    req = urllib.request.Request(NEBIH_LAW_LIST_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
        # PDF link keresése: kiadas + ELELMISZER + jogszabalygyujtemeny
        pattern = r'(/documents/[^"\']+ELELMISZER[^"\']*jogszabalygyujtemeny[^"\']*\.pdf)'
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            pdf_path = matches[0]
            if pdf_path.startswith("/"):
                return f"https://portal.nebih.gov.hu{pdf_path}"
            return pdf_path
        return None
    except Exception as e:
        print(f"⚠️  NÉBIH PDF URL keresés hiba: {e}", file=sys.stderr)
        return None


def download_pdf(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(path, "wb") as f:
            f.write(resp.read())


def extract_text(pdf_path):
    if fitz is None:
        return ""
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def parse_edition_number(text):
    """Kinyeri a kiadásszámot a PDF szövegből (pl. '132. kiadás')"""
    m = re.search(r'(\d+)\.\s*kiadás', text)
    return int(m.group(1)) if m else 0


def find_new_regulations(text):
    """Keres piros színnel jelölt új előírásokat a PDF-ben"""
    # Ha PyMuPDF elérhető, a piros színű szövegeket is ki tudjuk nyerni
    new_items = re.findall(r'(?:🆕|NEW|ÚJ|piros).*?(?:\n|$)', text, re.IGNORECASE)
    return new_items


def fetch_news():
    """NÉBIH friss hírek scraping"""
    req = urllib.request.Request(NEBIH_NEWS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
        # Hírcímek keresése (általában <h2>/<h3>/<a> tag-ekben)
        titles = re.findall(r'<h[23][^>]*>\s*<a[^>]*>(.*?)</a>', html, re.DOTALL)
        links = re.findall(r'<a href="(/[^"]+)"[^>]*>.*?</a>', html, re.DOTALL)
        items = []
        for i, title in enumerate(titles[:10]):
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            link = ""
            if i < len(links):
                link = f"https://portal.nebih.gov.hu{links[i]}" if links[i].startswith("/") else links[i]
            items.append({"title": title_clean, "link": link})
        return items
    except Exception as e:
        print(f"⚠️  NÉBIH hírek hiba: {e}", file=sys.stderr)
        return []


def run():
    """Fő belépési pont — hetente (PDF) + naponta (hírek)"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "news"

    if mode == "pdf":
        run_pdf()
    else:
        run_news()


def run_pdf():
    """Heti PDF ellenőrzés"""
    pdf_url = get_latest_pdf_url()
    if not pdf_url:
        print("⚠️  NÉBIH PDF URL nem található")
        return

    # Állapot ellenőrzés
    state = db.get_crawl_state("nebih_pdf")
    last_pdf_url = state.get("last_cursor", "")

    if pdf_url == last_pdf_url:
        print("NO_NEW — ugyanaz a PDF kiadás")
        return

    # Letöltés
    os.makedirs(PDF_DIR, exist_ok=True)
    local_path = os.path.join(PDF_DIR, hashlib.md5(pdf_url.encode()).hexdigest() + ".pdf")

    try:
        download_pdf(pdf_url, local_path)
        text = extract_text(local_path)
        if not text:
            print("⚠️  NÉBIH PDF szövegkinyerés sikertelen")
            return

        edition = parse_edition_number(text)
        new_regs = find_new_regulations(text)

        item_id = db.add_item(
            source="nebih",
            source_id=pdf_url,
            title=f"NÉBIH jogszabálygyűjtemény — {edition}. kiadás",
            url=pdf_url,
            published_at=None,
            raw_json=json.dumps({
                "edition": edition,
                "pdf_url": pdf_url,
                "new_regulations_count": len(new_regs),
                "new_regulations": new_regs[:10],
            }, ensure_ascii=False),
        )
        if item_id:
            print(f"📘 NÉBIH {edition}. kiadás — {len(new_regs)} új előírás")

        db.set_crawl_state("nebih_pdf", pdf_url)

    except Exception as e:
        print(f"⚠️  NÉBIH PDF feldolgozás hiba: {e}", file=sys.stderr)


def run_news():
    """Napi hírfigyelés"""
    news_items = fetch_news()
    new_count = 0
    for item in news_items:
        if not item["title"]:
            continue
        source_id = f"nebih_news_{hashlib.md5(item['title'].encode()).hexdigest()}"
        item_id = db.add_item(
            source="nebih",
            source_id=source_id,
            title=item["title"][:500],
            url=item.get("link", ""),
            published_at=None,
            raw_json=json.dumps(item, ensure_ascii=False),
        )
        if item_id:
            new_count += 1
            print(f"📰 NÉBIH: {item['title'][:80]}")
    print(f"✅ NÉBIH hírek: {new_count} új")


if __name__ == "__main__":
    run()