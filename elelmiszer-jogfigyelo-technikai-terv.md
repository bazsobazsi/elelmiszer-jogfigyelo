# Élelmiszeripari Jogszabály- és Szabványfigyelő — Konkrét Technikai Terv

## 1. Cél és hatókör

AI-alapú, magyar nyelvű B2B rendszer élelmiszeripari cégek minőségbiztosítási vezetőinek:
- **EU-s és magyar jogszabályváltozások** automatikus detektálása (napi)
- **RASFF riasztások** termékspecifikus szűréssel (napi)
- **Szabványfrissítések** (BRCGS/IFS/FSSC/ISO 22000) figyelése
- **AI összefoglaló** magyarul, hatásvizsgálattal ("mit kell tennie az ügyfélnek?")
- **Heti e-mail jelentés** a minőségbiztosítási vezetőnek
- **Dark dashboard** mobilbarát megjelenítéssel

## 2. Projekt struktúra

```
/home/bazsohome/elelmiszer-jogfigyelo/
├── serve.py                  # Flask dashboard (port 8768)
├── static/                   # CSS/JS (dark theme, mobilfirst)
├── templates/                # HTML
├── crawlers/
│   ├── __init__.py
│   ├── eurlex.py             # EUR-Lex RSS figyelő
│   ├── rasff.py              # RASFF API lekérdező
│   ├── kozlony.py            # Magyar Közlöny figyelő (adaptált)
│   └── nebih.py              # NÉBIH jogszabálygyűjtemény PDF diff
├── ai/
│   ├── __init__.py
│   ├── classify.py           # Relevancia-osztályozó
│   ├── summarize.py          # Magyar nyelvű összefoglaló
│   └── impact.py             # Hatásvizsgálat ("kit érint, mit kell tenni")
├── db.py                     # SQLite schema + helperek
├── notify.py                 # Telegram/e-mail értesítő
├── weekly_report.py          # Heti összefoglaló generáló
├── requirements.txt
├── install.sh                # Docker/Coolify deploy + cron setup
└── config.yaml               # Ügyfélprofilok, szűrők, webhook-ok
```

## 3. Adatbázis séma (SQLite)

```sql
-- Források: eurlex, rasff, kozlony, nebih, szabvany
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- eurlex/rasff/kozlony/nebih/szabvany
    source_id TEXT UNIQUE,             -- dedup kulcs (URL / RASFF ref / MK szám)
    title TEXT NOT NULL,
    url TEXT,
    published_at TEXT,                 -- ISO dátum
    raw_json TEXT,                     -- nyers adat forrás szerint
    fetched_at TEXT DEFAULT (datetime('now'))
);

-- AI feldolgozás eredménye
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    relevant INTEGER DEFAULT 0,        -- 0/1 releváns-e a profilra
    category TEXT,                     -- jogszabaly/riasztas/szabvany/egyeb
    product_groups TEXT,               -- JSON array: mely termékcsoportokra hat
    impact_summary TEXT,               -- magyar nyelvű összefoglaló
    action_required TEXT,              -- mit kell tennie (javaslat)
    deadline TEXT,                     -- kinyert határidő (ha van)
    standards_affected TEXT,           -- JSON: pl ["BRCGS", "HACCP"]
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ügyfélprofil
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                -- ügyfél/telephely neve
    product_groups TEXT NOT NULL,      -- JSON: ["húskészítmény", "tejtermék"]
    standards TEXT NOT NULL,           -- JSON: ["BRCGS", "IFS Food"]
    keywords TEXT,                     -- extra keresőszavak
    notification_channel TEXT,         -- telegram/e-mail/webhook
    notification_target TEXT,          -- chat_id / email / URL
    active INTEGER DEFAULT 1
);

-- Küldött értesítések (ne legyen duplikáció)
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    item_id INTEGER,
    sent_at TEXT DEFAULT (datetime('now')),
    UNIQUE(profile_id, item_id)
);

-- Crawler állapot (utolsó feldolgozott)
CREATE TABLE crawl_state (
    source TEXT PRIMARY KEY,
    last_cursor TEXT,                  -- utolsó item id / dátum
    last_run TEXT
);
```

## 4. Crawler modulok

### 4.1 EUR-Lex RSS (eurlex.py)

**Forrás:** EUR-Lex előredefiniált RSS feed-ek

```
# Food safety jogalkotás (SUBDOM=LEGISLATION, DC_CODED=13):
https://eur-lex.europa.eu/search.html?DB_COLL=eli&DC_CODED=13&lang=hu&type=advanced&rss=true

# EFSA-kapcsolódó / SANTE:
https://eur-lex.europa.eu/search.html?SUBDOM_INIT=LEGISLATION&DTS_SUBDOM=LEGISLATION&DC_CODED=13&lang=hu&rss=true
```

**Megjegyzés:** Az EUR-Lex RSS URL-ek beállítását a webes felületen kell generálni (search + RSS gomb), és tesztelni kell, hogy a paraméterek élő feedet adnak-e. Ha nem, fallback: EUR-Lex oldal scraping + `web_extract`.

**Feldolgozás:**
1. RSS XML lekérés (`urllib` vagy `requests`)
2. Item-ek kinyerése (title, link, pubDate)
3. `source_id` = ELI URL (dedup)
4. Csak új itemek → analyses táblába

**Frekvencia:** napi 1x (cron 08:00)

### 4.2 RASFF (rasff.py)

**Forrás:** RASFF nyilvános keresőfelület (webes) + ismert API-minták

**Megoldás kész scraperrel (nem kell 3rd party API kulcsot venni):**
- Apify actor (`automation-lab/eu-rasff-food-safety-alerts-scraper`) — fizetős per-alert (~$0.0001), 31k riasztás archívum
- **VAGY saját scraping:** RASFF portálon `dateFrom` paraméteres keresés + JSON kinyerés

**Ajánlott: saját scraping** (Zsolt elve: ne függjünk 3rd party fizetős API-tól, és a RASFF portál nem gátolja a rendszeres lekérést észszerű gyakorisággal).

**Feldolgozás:**
1. Lekérdezés: utolsó 24-48 óra riasztásai (`web_search`/`web_extract` vagy közvetlen HTTP)
2. Adatpontok: reference, subject, productCategory, productType, riskDecision, notifyingCountry, originCountries, hazards, measuresTaken
3. `source_id` = rasff reference (pl. `2026.1234`)
4. AI osztályozás: releváns-e az ügyfél termékcsoportjára

**Frekvencia:** napi 2x (08:00 és 14:00) — RASFF napközben is frissül

### 4.3 Magyar Közlöny (kozlony.py)

**Adaptáció a meglévő MK Figyelő scriptből** (`~/.hermes/scripts/kozlony_figyelo_v2.py`):
- RSS: `https://magyarkozlony.hu/feed` — már működik
- Az élelmiszeripari domain kulcsszavakkal kell újradefiniálni:
  - élelmiszer, élelmiszerbiztonság, élelmiszerlánc, NÉBIH, élelmiszeripar
  - HACCP, élelmiszerhigiénia, jelölés, címkézés
  - adalékanyag, aroma, szennyezőanyag, mikrobiológiai
  - Magyar Élelmiszerkönyv, önellenőrzés
  - termékvisszahívás, RASFF
  - konkrét termékek: hús, tej, tejtermék, gabona, cukrász
- PDF → szöveg → kulcsszavas találat + jogszabályhivatkozás regex

**Frekvencia:** naponta 09:00

### 4.4 NÉBIH (nebih.py)

**Források:**
1. **Jogszabálygyűjtemény PDF:** `https://portal.nebih.gov.hu/-/elelmiszer-jogszabalyok-jegyzeke` → a legújabb kiadás PDF linkje
2. **Friss hírek:** `https://portal.nebih.gov.hu/friss-hirek`

**Megoldás:**
- Hetente egyszer letölteni a legfrissebb PDF-et → PyMuPDF → szöveg
- Összehasonlítani az előző kiadással (diff):
  - Megjelent-e újabb kiadás (verziószám/kiadásszám változás)
  - A "piros" jelöléssel kiemelt új előírások → AI kinyeri és magyarázza
- Friss hírek: napi 1x scraping + szűrés

**Frekvencia:** PDF hetente (hétfő 10:00), hírek naponta

### 4.5 Szabványfrissítések (szabvany)

**Források:** szabványweboldalak (brcgs.com, ifs-certification.com, fssc.com, iso.org)

**Megoldás:** havi 1x ellenőrzés (nem változnak sűrűn):
- brcgs.com hírek/kiadások oldal
- ifs-certification.com news
- fssc.com news
- web_search: "BRCGS new issue 2026", "IFS Food update", stb.

**Frekvencia:** hetente 1x (szombat 10:00) — olcsó, megbízható

## 5. AI feldolgozási réteg

### 5.1 Osztályozó (classify.py)

**Bemenet:** nyers item (title + szöveg/PDF részlet)
**Prompt:** 
```
Te egy élelmiszeripari minőségbiztosítási szakértő vagy. 
Elemezd a következő szöveget:
{tartalom}

Döntsd el:
1. Releváns-e élelmiszeripari minőségbiztosítási szempontból? (0/1)
2. Kategória: jogszabaly / riasztas / szabvany / egyeb
3. Érintett termékcsoportok: [lista a profil alapján]
4. Érintett szabványok: [BRCGS/IFS/FSSC 22000/ISO 22000/HACCP — ha köthető]

Válasz JSON formátumban:
{"relevant": 0|1, "category": "...", "product_groups": [...], "standards": [...]}
```

**Költség:** ~200 token/item × napi ~10-30 item = elenyésző (openrouter free/olcsó modell is elég)

### 5.2 Összefoglaló (summarize.py)

**Bemenet:** relevant item-ek (profilonként szűrve)
**Prompt:** magyar nyelvű, tömör B2B stílusú összefoglaló:
```
Magyar nyelvű, tömör összefoglaló élelmiszeripari minőségbiztosítási vezetőnek:
- Mi változott? (1-2 mondat)
- Kit érint? (termékcsoportok)
- Milyen határidők vannak?
- Mit kell tennie? (konkrét lépések)
```
**Kimenet:** impact_summary + action_required + deadline mezőkbe

### 5.3 Határidő-kinyerés

A summarize részeként: `deadline` mező — regex `\d{4}\.\s*(január|február|...|december)\s*\d{1,2}\.` + LLM verifikáció

## 6. Dashboard (serve.py)

**Tech:** Flask + SQLite + dark theme (megszokott minták: holaviz/traffipax/levegominoseg)

**Port:** 8768 (külön port, ahogy szoktuk)

**Oldalak:**
1. **Fő (napi áttekintés):** Ma releváns változások listája — kártyák: kategória ikon, cím, összefoglaló, határidő, érintett szabványok tag-ek
2. **Szűrők:** source (EUR-Lex/RASFF/Közlöny/NÉBIH), profil, termékcsoport, kategória, dátumtartomány
3. **Részletek:** egy item teljes analízise (nyers + AI összefoglaló)
4. **Profilok:** ügyfélprofilok CRUD (product_groups, standards, notification beállítások)
5. **Archívum:** kereshető listázás, export CSV

**API endpointok** (a jövőbeli mobil apphoz):
- `GET /api/items?days=7&profile=1&category=...`
- `GET /api/items/<id>`
- `GET /api/profiles`
- `GET /api/stats` — heti számok dashboard boxokhoz

**Mobilfirst:** CSS grid, kártya-layout, adatok görgethetők (Zsolt preferencia)

## 7. Értesítések (notify.py)

**Csatornák:**
1. **Telegram** — azonnali napi értesítés a fő chatbe / ügyfélnek
2. **E-mail** — heti összefoglaló (html formázott)
3. **Webhook** — későbbi ügyfél-integrációkhoz (Slack/Teams)

**Napi Telegram üzenet formátum:**
```
🍽️ Élelmiszer-jogfigyelő — 2026-09-13
📊 3 releváns változás

🔴 JOGSZABÁLY (EU)
📄 EU 2025/1441 — importellenőrzés módosítás
🏷️ szennyezőanyagok, harmadik országok
📝 A RASFF-értesítések alapján frissítették az ellenőrzési listákat...
⏰ Hatályos: 2025-08-01
🔗 https://eur-lex.europa.eu/...

🟡 RIASZTÁS (RASFF)
📄 Allergén bejelentés — mustár és tojás dressingben
🏷️ allergének, címkézés
📝 ELLENŐRZÉS: alszállítói termékek címkézése...

🔵 SZABVÁNY (NÉBIH)
📄 BPA tilalom élelmiszerrel érintkező anyagokban
📝 A csomagolóanyag-beszállítók tanúsítványainak ellenőrzése...

✅ Nincs változás: FSSC 22000, ISO 22000 (folyamatosan érvényes)
```

**Heti e-mail:** hétfő reggel — összes releváns változás heti bontásban + nyitott határidők lista (profilok szerint csoportosítva)

## 8. Cron beállítások (Hermes cron)

| Job | Schedule | Mit futtat | Output |
|---|---|---|---|
| eurlex_daily | napi 08:00 | eurlex.py + classify | Telegram napi digest 17:00 |
| rasff_daily | napi 08:00, 14:00 | rasff.py + classify | Beolvad a napi digestbe |
| kozlony_daily | napi 09:00 | kozlony.py (osztályozóval) | Beolvad a napi digestbe |
| nebih_hírek | napi 10:00 | nebih.py hírek | Beolvad a napi digestbe |
| nebih_pdf | hetente hétfő 10:30 | nebih.py PDF diff | Külön értesítés, ha új kiadás |
| szabvany_week | hetente szombat 10:00 | szabvany.py | Beolvad a heti riportba |
| weekly_report | hetente hétfő 07:00 | weekly_report.py | E-mail + Telegram |
| digest_17 | napi 17:00 | összeállítja a napi digestet | Telegram |

## 9. Install.sh (Docker/Coolify)

```bash
#!/bin/bash
# Telepítés: bármilyen Linux eszközön fusson

sudo apt-get update && sudo apt-get install -y python3 python3-pip sqlite3 curl

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Cron beállítás (system crontab vagy Hermes cron)
python3 db.py --init

echo "Kész. Dashboard: http://localhost:8768"
```

**Requirements:**
```
flask
requests
pymupdf
feedparser  # RSS könnyebben
beautifulsoup4
```

## 10. Fejlesztési ütemterv (MVP)

| Fázis | Feladat | Idő |
|---|---|---|
| 0 | Projekt scaffold, db.py, config.yaml | 0,5 nap |
| 1 | eurlex.py + classify.py (EUR-Lex RSS + AI osztályozás) | 1 nap |
| 2 | kozlony.py adaptáció (élelmiszeripari kulcsszavak) | 1 nap |
| 3 | rasff.py (saját scraping) | 1 nap |
| 4 | nebih.py (PDF diff + hírek) | 1,5 nap |
| 5 | Dashboard (serve.py + templates) | 2 nap |
| 6 | notify.py + Weekly report | 1 nap |
| 7 | Cron beállítás + tesztelés éles forrásokkal | 1 nap |
| **Összesen** | | **~9 munkanap** |

## 11. Kockázatok

1. **EUR-Lex RSS URL-ek változhatnak** — a cron job hiba esetén fallbackre vált (web_extract)
2. **RASFF scraping** — a portál szerkezete változhat; a `source_id` dedup miatt nem veszünk el adatot, de hézag lehet a letapogatatlan időszakban → heti RASFF archívum ellenőrzés a weekly report részeként
3. **NÉBIH PDF formátum** — a kiadások között változhat a szerkezet; a diff a teljes szövegen működik, nem a formátumon
4. **AI hallucináció** — jogi összefoglalónál a prompt tartalmazza: "ha nem vagy biztos, írd be, hogy ellenőrizd az eredeti forrást" + minden elemhez link az eredeti dokumentumra
5. **Free modell pontossága** — osztályozáshoz elég; összefoglalóhoz/határnapon deepseek vagy jobb modell ajánlott (Zsolt elve: pontosság > ár élesben)

## 12. Üzleti modell

**Első ügyfél:** a meglévő jelölt — minőségbiztosítási vezető

**Árazási javaslat:**
- Bevezetés: 300-500 eFt egyszeri (profil- és termékcsoport-beállítás, 30 nap tesztadat)
- Havi díj: 50-90 eFt/ügyfél (profilonként, extra telephely +30%)
- A rendszer multi-tenant: több ügyfél ugyanaz a pipeline, csak más profil/szűrés

**Mit vásárol az ügyfél:**
- Nem kell naponta böngésznie EUR-Lexet, RASFF-ot, Közlönyt, NÉBIH-et
- Magyar nyelvű, szakértői szintű összefoglaló minden változásról
- Azonnal tudja, ha az Ő termékkörét érinti valami (nem 3 hónappal később fedezi fel)
- Auditra kész: nyomonkövethető, hogy mikor értesült a változásról (compliance bizonyíték)