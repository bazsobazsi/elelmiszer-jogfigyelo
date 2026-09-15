#!/usr/bin/env python3
"""
Flask dashboard — élelmiszeripari jogszabályfigyelő
Dark theme, mobilfirst, chart-ek, szűrők
"""
import json
import os
import sys

from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

# DB auto-init ha nem létezik
if not os.path.exists(db.DB_PATH):
    print("⚠️  DB nem található — inicializálás...")
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "db.py")])
    print("✅ DB inicializálva")

app = Flask(__name__)

# ── HTML TEMPLATE (dark theme, mobilfirst) ──

INDEX_HTML = """<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🍽️ Élelmiszer-jogfigyelő</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0a0a0f; color: #e0e0e0; padding: 16px; }
.header { border-bottom: 1px solid #1a1a2e; padding-bottom: 12px; margin-bottom: 16px; }
.header h1 { font-size: 1.4rem; color: #fff; }
.header .sub { font-size: 0.85rem; color: #888; margin-top: 4px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-box { background: #12121a; border: 1px solid #1a1a2e; border-radius: 8px;
            padding: 12px 16px; flex: 1; min-width: 100px; text-align: center; }
.stat-box .num { font-size: 1.6rem; font-weight: 700; color: #4fc3f7; }
.stat-box .label { font-size: 0.78rem; color: #888; margin-top: 4px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.filters select, .filters input { background: #12121a; border: 1px solid #2a2a3e;
       color: #e0e0e0; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; }
.filters button { background: #4fc3f7; color: #0a0a0f; border: none; padding: 8px 16px;
       border-radius: 6px; font-weight: 600; cursor: pointer; }
.card { background: #12121a; border: 1px solid #1a1a2e; border-radius: 10px;
        padding: 14px; margin-bottom: 10px; }
.card .source { font-size: 0.75rem; color: #666; text-transform: uppercase; }
.card .title { font-size: 1rem; font-weight: 600; color: #fff; margin: 4px 0; }
.card .meta { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0; }
.tag { background: #1a1a2e; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; color: #aaa; }
.tag.red { background: #2e1a1a; color: #f77; }
.tag.yellow { background: #2e2a1a; color: #ff7; }
.tag.blue { background: #1a1a2e; color: #77f; }
.tag.purple { background: #2e1a3e; color: #c77; }
.tag.green { background: #1a2e1a; color: #7f7; }
.card .summary { font-size: 0.85rem; color: #bbb; line-height: 1.4; }
.card .actions { font-size: 0.82rem; color: #4fc3f7; margin-top: 6px; }
.card .deadline { font-size: 0.8rem; color: #ff7; margin-top: 4px; }
.card .link { display: inline-block; margin-top: 6px; font-size: 0.8rem; color: #4fc3f7; text-decoration: none; }
a { color: #4fc3f7; }
.empty { text-align: center; padding: 40px; color: #666; }
.error-msg { background: #2e1a1a; border: 1px solid #5c2a2a; border-radius: 8px; padding: 12px; color: #f77; margin-bottom: 12px; }
@media (max-width: 600px) {
  .stat-box { min-width: calc(50% - 4px); }
  .filters select { width: 100%; }
}
</style>
</head>
<body>
<div class="header">
  <h1>🍽️ Élelmiszer-jogfigyelő</h1>
  <div class="sub">AI-alapú jogszabály- és szabványfigyelés</div>
</div>

<div id="error" style="display:none;" class="error-msg"></div>

<div class="stats" id="stats">
  <div class="stat-box"><div class="num" id="stat-total">-</div><div class="label">Ma összesen</div></div>
  <div class="stat-box"><div class="num" id="stat-relevant">-</div><div class="label">Releváns</div></div>
  <div class="stat-box"><div class="num" id="stat-sources">-</div><div class="label">Források</div></div>
</div>

<div class="filters">
  <select id="filter-source">
    <option value="">Minden forrás</option>
    <option value="eurlex">EUR-Lex</option>
    <option value="rasff">RASFF</option>
    <option value="kozlony">Magyar Közlöny</option>
    <option value="nebih">NÉBIH</option>
    <option value="szabvany">Szabványok</option>
    <option value="eu_guidance">EU Guidance</option>
    <option value="nak_ghp">NAK GMP</option>
  </select>
  <select id="filter-category">
    <option value="">Minden kategória</option>
    <option value="jogszabaly">Jogszabály</option>
    <option value="modositas">Módosítás</option>
    <option value="riasztas">Riasztás</option>
    <option value="iranymutatas">Irányítás</option>
    <option value="GMP_utmutato">GMP</option>
    <option value="export">Export</option>
    <option value="szabvany">Szabvány</option>
    <option value="egyeb">Egyéb</option>
  </select>
  <select id="filter-relevant">
    <option value="">Minden</option>
    <option value="1">Csak releváns</option>
  </select>
  <button onclick="loadItems()">🔍 Szűrés</button>
</div>

<div id="items"></div>

<script>
function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 8000);
}

async function loadItems() {
  const source = document.getElementById('filter-source').value;
  const category = document.getElementById('filter-category').value;
  const relevant = document.getElementById('filter-relevant').value;
  const params = new URLSearchParams({ source, category, relevant });
  try {
    const res = await fetch('/api/items?' + params);
    const data = await res.json();
    renderItems(data);
  } catch(e) {
    showError('Hiba az adatok betöltésekor: ' + e.message);
  }
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stat-total').textContent = data.total_items || '0';
    document.getElementById('stat-relevant').textContent = data.relevant_count || '0';
    document.getElementById('stat-sources').textContent = data.sources || '0';
  } catch(e) {
    showError('Hiba a statisztika betöltésekor');
  }
}

function renderItems(items) {
  const container = document.getElementById('items');
  if (!items || items.length === 0) {
    container.innerHTML = '<div class="empty">📭 Nincs találat</div>';
    return;
  }
  container.innerHTML = items.map(item => {
    const sourceEmoji = {eurlex:'🔴', rasff:'🟡', kozlony:'🔵', nebih:'📘', szabvany:'🟣', eu_guidance:'📋', nak_ghp:'📕'};
    const emoji = sourceEmoji[item.source] || '📄';
    const catLabel = {jogszabaly:'Jogszabály', modositas:'Módosítás', jovahagyas:'Jóváhagyás', riasztas:'Riasztás', iranymutatas:'Irányítás', GMP_utmutato:'GMP Útmutató', export:'Export', egyeb:'Egyéb'};
    const catTagClass = {jogszabaly:'red', modositas:'red', jovahagyas:'blue', riasztas:'yellow', iranymutatas:'blue', GMP_utmutato:'purple', export:'green', egyeb:''};

    let groups = '';
    try { const g = JSON.parse(item.product_groups || '[]'); if(g.length) groups = g.join(', '); } catch(e) {}
    let standards = '';
    try { const s = JSON.parse(item.standards_affected || '[]'); if(s.length) standards = s.join(', '); } catch(e) {}
    let summary = item.impact_summary || '';
    let action = item.action_required || '';
    let deadline = item.deadline || '';

    return `<div class="card">
      <div class="source">${emoji} ${item.source.toUpperCase()} · ${catLabel[item.category] || item.category}</div>
      <div class="title">${escapeHtml(item.title)}</div>
      <div class="meta">
        ${groups ? `<span class="tag">🏷️ ${escapeHtml(groups)}</span>` : ''}
        ${standards ? `<span class="tag">📋 ${escapeHtml(standards)}</span>` : ''}
        ${item.category ? `<span class="tag ${catTagClass[item.category]||''}">${catLabel[item.category]||item.category}</span>` : ''}
      </div>
      ${summary ? `<div class="summary">📝 ${escapeHtml(summary)}</div>` : ''}
      ${action ? `<div class="actions">⚡ ${escapeHtml(action)}</div>` : ''}
      ${deadline ? `<div class="deadline">⏰ Határidő: ${escapeHtml(deadline)}</div>` : ''}
      ${item.url ? `<a class="link" href="${escapeHtml(item.url)}" target="_blank">🔗 Forrás megnyitása →</a>` : ''}
    </div>`;
  }).join('');
}

function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadStats();
loadItems();
</script>
</body>
</html>"""


# ── API ENDPOINTS ──

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/items")
def api_items():
    source = request.args.get("source", "")
    category = request.args.get("category", "")
    relevant = request.args.get("relevant", "")

    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    items = db.get_items_with_analysis(limit=limit, offset=offset)

    # Szűrés
    filtered = []
    for item in items:
        if source and item.get("source") != source:
            continue
        if category and item.get("category") != category:
            continue
        if relevant == "1" and not item.get("relevant"):
            continue
        filtered.append(item)

    return jsonify(filtered)


@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_stats())


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})

@app.route("/api/daily")
def api_daily():
    import notify
    items = db.get_daily_digest()
    return jsonify(items)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8768))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"🍽️  Élelmiszer-jogfigyelő dashboard: http://0.0.0.0:{port}")
    try:
        app.run(host="0.0.0.0", port=port, debug=debug)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)