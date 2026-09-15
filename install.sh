#!/bin/bash
# Élelmiszer-jogfigyelő telepítő — bármilyen Linux eszközön fusson
set -e

echo "🍽️  Élelmiszer-jogfigyelő telepítő"

# 1. Függőségek
if ! command -v python3 &>/dev/null; then
    echo "📦 Python3 telepítése..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv sqlite3
fi

# 2. Virtuális környezet
if [ ! -d "venv" ]; then
    echo "🔧 Virtuális környezet létrehozása..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 3. Adatbázis inicializálás
echo "🗄️  Adatbázis inicializálása..."
python3 db.py

# 4. Teszt: EUR-Lex crawler
echo "🧪 EUR-Lex crawler teszt..."
python3 crawlers/eurlex.py 2>&1 | head -20

# 5. Indítási útmutató
echo ""
echo "✅ Kész!"
echo ""
echo "Dashboard indítása:"
echo "  cd $(pwd) && source venv/bin/activate && python3 serve.py"
echo "  → http://localhost:8768"
echo ""
echo "Crawler futtatása:"
echo "  python3 crawlers/eurlex.py    # EUR-Lex"
echo "  python3 crawlers/kozlony.py   # Magyar Közlöny"
echo "  python3 crawlers/rasff.py     # RASFF"
echo "  python3 crawlers/nebih.py     # NÉBIH (news)"
echo "  python3 crawlers/nebih.py pdf # NÉBIH (jogszabálygyűjtemény)"
echo ""
echo "Cron beállítások (Hermes cron):"
echo "  lásd a tervben: ~/.hermes/plans/elelmiszer-jogfigyelo-technikai-terv.md"