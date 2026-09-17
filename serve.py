#!/usr/bin/env python3
"""
Flask dashboard — élelmiszeripari jogszabályfigyelő
Dark theme, mobilfirst, chart-ek, szűrők
"""
import json
import os
import sys
import logging

from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

# Logolás beállítása — minden kimenjen stdout-ra
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

# Admin jelszó ellenőrzés
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def require_auth():
    """GET kérésekhez auth header ellenőrzés (Bearer token)"""
    auth = request.headers.get("Authorization", "")
    if ADMIN_PASSWORD and not auth.startswith("Bearer "):
        return False
    token = auth.replace("Bearer ", "", 1) if auth else ""
    return (not ADMIN_PASSWORD) or (token == ADMIN_PASSWORD)

def require_auth_post():
    """POST kérésekhez auth ellenőrzés JSON body-ból vagy header-ből"""
    if not ADMIN_PASSWORD:
        return True
    data = request.get_json(silent=True) or {}
    pw = data.get("admin_password", "") or request.headers.get("X-Admin-Key", "")
    return pw == ADMIN_PASSWORD

# DB auto-init ha nem létezik
if not os.path.exists(db.DB_PATH):
    print("⚠️  DB nem található — inicializálás...")
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "db.py")])
    print("✅ DB inicializálva")

# Auto-seed: ha nincs adat, seed_data.json-ból töltjük
seed_lock = os.path.join(db.DB_DIR, ".seeded")
if not os.path.exists(seed_lock):
    seed_path = os.path.join(os.path.dirname(__file__), "seed_data.json")
    if os.path.exists(seed_path):
        try:
            import subprocess as _sub, sys as _sys
            r = _sub.run([_sys.executable, os.path.join(os.path.dirname(__file__), "seed.py")],
                        capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                print("✅ Auto-seed: seed_data.json betöltve")
            else:
                print(f"⚠️  Auto-seed hiba: {r.stderr[-200:]}")
            open(seed_lock, "w").close()
        except Exception as e:
            print(f"⚠️  Auto-seed exception: {e}")

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
.nav { display:flex; gap:6px; }
.nav-btn { background:#1a1a2e; border:1px solid #2a2a3e; color:#888; padding:6px 12px; border-radius:6px; cursor:pointer; font-size:0.82rem; }
.nav-btn.active { background:#4fc3f7; color:#0a0a0f; border-color:#4fc3f7; }
.form-group { margin-bottom:10px; }
.form-group label { display:block; font-size:0.82rem; color:#aaa; margin-bottom:3px; }
.form-input { background:#1a1a2e; border:1px solid #2a2a3e; color:#e0e0e0; padding:8px; border-radius:6px; font-size:0.85rem; width:100%; max-width:400px; }
.btn-primary { background:#4fc3f7; color:#0a0a0f; border:none; padding:8px 16px; border-radius:6px; font-weight:600; cursor:pointer; }
.btn-secondary { background:#2a2a3e; color:#e0e0e0; border:none; padding:8px 16px; border-radius:6px; font-weight:600; cursor:pointer; }
.form-status { font-size:0.82rem; color:#4fc3f7; }
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
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div>
      <h1>🍽️ Élelmiszer-jogfigyelő</h1>
      <div class="sub">AI-alapú jogszabály- és szabványfigyelés</div>
    </div>
    <div class="nav">
      <button class="nav-btn active" onclick="showTab('dashboard')" id="tab-dash">📊 Dashboard</button>
      <button class="nav-btn" onclick="showTab('settings')" id="tab-set">⚙️ Beállítások</button>
    </div>
  </div>
</div>

<div id="page-dashboard">
  <div id="error" style="display:none;" class="error-msg"></div>
  <div class="stats" id="stats">
    <div class="stat-box"><div class="num" id="stat-total">-</div><div class="label">Összes item</div></div>
    <div class="stat-box"><div class="num" id="stat-relevant">-</div><div class="label">Releváns</div></div>
    <div class="stat-box"><div class="num" id="stat-sources">-</div><div class="label">Források</div></div>
  </div>
  <div class="filters" id="filters">
      <select id="filter-source" onchange="loadItems()">
        <option value="">Minden forrás</option>
      </select>
      <select id="filter-category" onchange="loadItems()">
        <option value="">Minden kategória</option>
      </select>
      <select id="filter-relevant" onchange="loadItems()">
        <option value="">Relevancia szerint</option>
        <option value="1">Csak releváns</option>
        <option value="0">Csak nem releváns</option>
      </select>
    </div>
  <div id="items"></div>
</div>

<div id="page-settings" style="display:none;">
  <h2 style="margin-bottom:12px;">📧 Email értesítés</h2>
  
  <div style="font-size:0.82rem; color:#aaa; background:#12121a; border:1px solid #2a2a3e; border-radius:6px; padding:10px; margin-bottom:12px;">
    <strong>Kötelező mezők:</strong> SMTP szerver, Port, Felhasználó, Jelszó, Feladó email, Címzett(ek).<br>
    Először add meg az <strong>admin jelszót</strong> lent → 🔓 Feloldás → utána módosíthatod a beállításokat.
  </div>
  
  <!-- Admin jelszó mező -->
  <div id="admin-section" class="card" style="margin-bottom:12px;">
    <div class="form-group"><label>Admin jelszó (a beállítások módosításához)</label>
      <div style="display:flex; gap:8px;">
        <input id="admin_pass" type="password" class="form-input" placeholder="A Coolify ADMIN_PASSWORD környezeti változó értéke" style="flex:1;">
        <button class="btn-secondary" onclick="unlockSettings()">🔓 Feloldás</button>
      </div>
    </div>
    <div id="admin-status" class="form-status"></div>
  </div>
  
  <!-- Jelenlegi beállítások összefoglaló -->
  <div id="settings-summary" class="card" style="margin-bottom:12px; display:none;">
    <div style="font-size:0.85rem;">
      <div id="summ-status" style="margin-bottom:6px;"></div>
      <div id="summ-to" style="color:#aaa; margin-bottom:2px;"></div>
      <div id="summ-cc" style="color:#aaa; margin-bottom:2px;"></div>
      <div id="summ-filters" style="color:#aaa; margin-bottom:2px;"></div>
      <div id="summ-from" style="color:#666; font-size:0.75rem; margin-top:4px;"></div>
    </div>
  </div>
  
  <div id="settings-form" style="display:none;">
    <div class="card">
    <div class="form-group"><label>SMTP szerver</label><input id="smtp_host" class="form-input" placeholder="smtp.gmail.com"></div>
    <div class="form-group"><label>Port</label><input id="smtp_port" class="form-input" value="587" placeholder="587"></div>
    <div class="form-group"><label>SMTP felhasználó</label><input id="smtp_user" class="form-input" placeholder="email@example.com"></div>
    <div class="form-group"><label>SMTP jelszó</label><input id="smtp_pass" type="password" class="form-input" placeholder="****"></div>
    <div class="form-group"><label>Feladó email</label><input id="from_email" class="form-input" placeholder="jogfigyelo@example.com"></div>
    <div class="form-group"><label>Címzett(ek) (vesszővel több is)</label><input id="to_email" class="form-input" placeholder="ugyfel1@ceg.hu, ugyfel2@ceg.hu"></div>
    <div class="form-group"><label>CC (kontroll — vesszővel több is)</label><input id="cc_email" class="form-input" placeholder="kontroll@ceg.hu"></div>
    <div class="form-group"><label>Termékszűrők (vesszővel)</label><input id="product_filters" class="form-input" placeholder="húskészítmény, tejtermék, pékáru"></div>
    <div class="form-group">
      <label><input id="email_enabled" type="checkbox"> Email értesítés bekapcsolva</label>
    </div>
    <div class="form-group"><label>Küldés időpontja (óra:perc)</label><input id="send_time" class="form-input" value="08:00" placeholder="08:00" style="width:120px;"></div>
    <div class="form-actions">
      <button class="btn-primary" onclick="saveSettings()">💾 Mentés</button>
      <button class="btn-secondary" onclick="testEmail()">📨 Teszt email</button>
    </div>
    <div id="settings-status" class="form-status" style="margin-top:8px;"></div>
  </div>
  
  <h2 style="margin:16px 0 8px;">🔄 Crawler vezérlés</h2>
  <div class="card" style="margin-bottom:12px;">
    <button class="btn-primary" onclick="runCrawlers()">▶️ Crawler-ek futtatása</button>
    <div id="crawl-status" class="form-status" style="margin-top:8px;"></div>
  </div>
  </div> <!-- settings-form vége -->
</div>

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
    if (!res.ok) { showError('API hiba (' + res.status + ')'); return; }
    const data = await res.json();
    if (!Array.isArray(data)) { showError('API nem lista'); return; }
    renderItems(data);
  } catch(e) {
    showError('Hiba: ' + e.message);
  }
}

async function loadFilters() {
  try {
    const res = await fetch('/api/filters');
    if (!res.ok) return;
    const data = await res.json();
    const sf = document.getElementById('filter-source');
    const cf = document.getElementById('filter-category');
    const sval = sf.value || '';
    const cval = cf.value || '';
    sf.innerHTML = '<option value="">Minden forrás</option>';
    (data.sources || []).forEach(s => {
      sf.innerHTML += `<option value="${s}"${s===sval?' selected':''}>${s}</option>`;
    });
    cf.innerHTML = '<option value="">Minden kategória</option>';
    (data.categories || []).forEach(c => {
      cf.innerHTML += `<option value="${c}"${c===cval?' selected':''}>${c}</option>`;
    });
  } catch(e) {}
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) { showError('API hiba (' + res.status + ')'); return; }
    const data = await res.json();
    document.getElementById('stat-total').textContent = data.total_items || '0';
    document.getElementById('stat-relevant').textContent = data.relevant_count || '0';
    document.getElementById('stat-sources').textContent = data.sources || '0';
  } catch(e) {
    showError('Hiba a statisztika betöltésekor: ' + e.message);
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
loadFilters();

// ── Settings / Tab functions ──
let settingsUnlocked = false;

function showTab(name) {
  document.getElementById('page-dashboard').style.display = name === 'dashboard' ? '' : 'none';
  document.getElementById('page-settings').style.display = name === 'settings' ? '' : 'none';
  document.getElementById('tab-dash').className = 'nav-btn' + (name === 'dashboard' ? ' active' : '');
  document.getElementById('tab-set').className = 'nav-btn' + (name === 'settings' ? ' active' : '');
  if (name === 'settings') loadSettings();
}

async function loadSettings() {
  try {
    const headers = {};
    const pw = getAdminPass();
    if (pw) headers['Authorization'] = 'Bearer ' + pw;
    const res = await fetch('/api/settings', {headers});
    if (!res.ok) { setStatus('settings-status', '❌ Hitelesítés szükséges', true); return; }
    const data = await res.json();
    const c = data.email_config || {};
    document.getElementById('smtp_host').value = c.smtp_host || '';
    document.getElementById('smtp_port').value = c.smtp_port || 587;
    document.getElementById('smtp_user').value = c.smtp_user || '';
    document.getElementById('from_email').value = c.from_email || '';
    document.getElementById('to_email').value = c.to_email || '';
    document.getElementById('cc_email').value = c.cc_email || '';
    let filters = c.product_filters || '';
    try { filters = JSON.parse(filters).join(', '); } catch(e) {}
    document.getElementById('product_filters').value = filters;
    document.getElementById('email_enabled').checked = c.enabled ? true : false;
    document.getElementById('send_time').value = c.send_time || '08:00';
    
    // Összefoglaló frissítése
    const summary = document.getElementById('settings-summary');
    if (c.to_email && c.enabled) {
      summary.style.display = '';
      document.getElementById('summ-status').textContent = '✅ Email értesítés BEKAPCSOLVA';
      document.getElementById('summ-status').style.color = '#7f7';
      document.getElementById('summ-to').textContent = '📨 Címzettek: ' + c.to_email;
      document.getElementById('summ-cc').textContent = '📨 CC: ' + (c.cc_email || '(nincs)');
      document.getElementById('summ-filters').textContent = '🏷️ Termékszűrők: ' + filters;
      document.getElementById('summ-from').textContent = 'Feladó: ' + (c.from_email || c.smtp_user || '?') + ' · Küldés: ' + (c.send_time || '08:00') + '-kor';
    } else if (c.to_email && !c.enabled) {
      summary.style.display = '';
      document.getElementById('summ-status').textContent = '⏸️ Email értesítés KI van kapcsolva';
      document.getElementById('summ-status').style.color = '#ff7';
      document.getElementById('summ-to').textContent = '📨 Címzettek: ' + c.to_email;
      document.getElementById('summ-cc').textContent = '📨 CC: ' + (c.cc_email || '(nincs)');
      document.getElementById('summ-filters').textContent = '🏷️ Termékszűrők: ' + filters;
      document.getElementById('summ-from').textContent = 'Feladó: ' + (c.from_email || c.smtp_user || '?');
    } else {
      summary.style.display = 'none';
    }
  } catch(e) {
    setStatus('settings-status', '❌ Hiba a beállítások betöltésekor', true);
  }
}

async function saveSettings() {
  const pw = getAdminPass();
  if (!pw && document.getElementById('admin_pass') && document.getElementById('admin_pass').offsetParent !== null) {
    setStatus('settings-status', '❌ Először add meg az admin jelszót és kattints a 🔓 Feloldás-ra', true);
    return;
  }
  const filters = document.getElementById('product_filters').value.split(',').map(s => s.trim()).filter(Boolean);
  const data = {
    smtp_host: document.getElementById('smtp_host').value,
    smtp_port: parseInt(document.getElementById('smtp_port').value) || 587,
    smtp_user: document.getElementById('smtp_user').value,
    smtp_pass: document.getElementById('smtp_pass').value,
    from_email: document.getElementById('from_email').value,
    to_email: document.getElementById('to_email').value,
    cc_email: document.getElementById('cc_email').value,
    product_filters: filters,
    enabled: document.getElementById('email_enabled').checked,
    send_time: document.getElementById('send_time').value || '08:00',
    admin_password: pw,
  };
  try {
    const res = await fetch('/api/settings', {method:'POST', body:JSON.stringify(data), headers:{'Content-Type':'application/json'}});
    const r = await res.json();
    if (r.status === 'ok') {
      setStatus('settings-status', '✅ Mentve');
      loadSettings(); // frissíti az összefoglalót
    } else if (res.status === 401) {
      setStatus('settings-status', '❌ ' + (r.error || 'Unauthorized — add meg az admin jelszót a 🔓 Feloldás gombbal'), true);
    } else {
      setStatus('settings-status', '❌ ' + (r.error || 'Ismeretlen hiba'), true);
    }
  } catch(e) {
    setStatus('settings-status', '❌ Hálózati hiba', true);
  }
}

async function testEmail() {
  setStatus('settings-status', '⏳ Teszt email küldése...');
  await saveSettings();
  const pw = getAdminPass();
  try {
    const res = await fetch('/api/test-email', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({admin_password: pw})});
    const r = await res.json();
    if (r.sent > 0) setStatus('settings-status', `✅ ${r.message}`);
    else setStatus('settings-status', '⚠️ ' + (r.error || r.message || 'Ismeretlen'), true);
  } catch(e) {
    setStatus('settings-status', '❌ Hálózati hiba: ' + e.message, true);
  }
}

async function runCrawlers() {
  setStatus('crawl-status', '⏳ Crawler-ek futtatása...');
  const pw = getAdminPass();
  try {
    const res = await fetch('/api/crawl', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({admin_password: pw})});
    const r = await res.json();
    let errs = [];
    for (const [name, res] of Object.entries(r)) {
      if (res.exit === 0) continue;
      errs.push(`${name}: ${res.error || res.err || 'exit='+res.exit}`);
    }
    if (errs.length === 0) {
      setStatus('crawl-status', '✅ Crawler kész. Frissítsd a dashboard-ot!');
    } else {
      setStatus('crawl-status', '⚠️ ' + errs.join(' | '), true);
    }
  } catch(e) {
    setStatus('crawl-status', '❌ Hálózati hiba: ' + e.message, true);
  }
}

function setStatus(id, msg, isError) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.color = isError ? '#f77' : '#4fc3f7'; }
}

function getAdminPass() {
  return document.getElementById('admin_pass') ? document.getElementById('admin_pass').value : '';
}

function unlockSettings() {
  const pw = getAdminPass();
  if (!pw) { setStatus('admin-status', 'Add meg az admin jelszót', true); return; }
  fetch('/api/settings', {headers:{'Authorization':'Bearer '+pw}})
    .then(r => { if(r.ok) { settingsUnlocked = true; document.getElementById('settings-form').style.display=''; setStatus('admin-status', '✅ Feloldva'); loadSettings(); }
      else { setStatus('admin-status', '❌ Rossz jelszó', true); } })
    .catch(e => setStatus('admin-status', '❌ Hiba: '+e.message, true));
}
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


@app.route("/api/filters")
def api_filters():
    try:
        return jsonify(db.get_filters())
    except Exception as e:
        log.error(f"Filters API error: {e}")
        return jsonify({"sources": [], "categories": []})


@app.route("/api/stats")
def api_stats():
    try:
        return jsonify(db.get_stats())
    except Exception as e:
        return jsonify({"total_items": 0, "relevant_count": 0, "sources": 0, "error": str(e)})


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        if ADMIN_PASSWORD and not require_auth_post():
            return jsonify({"error": "Unauthorized — add meg a helyes admin jelszót a kérésben (admin_password mező vagy X-Admin-Key header)"}), 401
        data = request.get_json(silent=True) or {}
        filters = data.get("product_filters", [])
        if isinstance(filters, str):
            filters = [s.strip() for s in filters.split(",") if s.strip()]
        try:
            db.save_email_config(
                host=data.get("smtp_host", ""),
                port=int(data.get("smtp_port", 587)),
                user=data.get("smtp_user", ""),
                passw=data.get("smtp_pass", ""),
                from_email=data.get("from_email", ""),
                to_email=data.get("to_email", ""),
                cc_email=data.get("cc_email", ""),
                filters=filters,
                enabled=data.get("enabled", False),
                send_time=data.get("send_time", "08:00"),
            )
            return jsonify({"status": "ok"})
        except Exception as e:
            log.error(f"Settings save error: {e}")
            return jsonify({"error": str(e)}), 500
    config = db.get_email_config()
    profiles = db.get_active_profiles()
    return jsonify({"email_config": config, "profiles": profiles})


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    """Crawler-ek futtatása — Coolify-ben vagy cron-ból hívható"""
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized"}), 401
    import subprocess, sys as _sys
    results = {}
    base = os.path.dirname(__file__)
    for name in ["crawler_nebih", "crawler_kozlony"]:
        try:
            r = subprocess.run([_sys.executable, os.path.join(base, f"{name}.py")],
                              capture_output=True, text=True, timeout=120)
            results[name] = {"exit": r.returncode, "out": r.stdout[-200:], "err": r.stderr[-200:]}
        except Exception as e:
            log.error(f"Crawl {name} error: {e}")
            results[name] = {"error": str(e)}
    try:
        db.init_db()
    except Exception as e:
        log.error(f"DB init after crawl: {e}")
    return jsonify(results)


@app.route("/api/send-digest", methods=["POST"])
def api_send_digest():
    """Email értesítés küldése a beállított címekre"""
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized"}), 401
    import smtplib, email.message
    config = db.get_email_config()
    if not config or not config.get("enabled"):
        return jsonify({"error": "Email nincs konfigurálva vagy letiltva"}), 400
    
    items = db.get_unnotified_relevant()
    if not items:
        return jsonify({"message": "Nincs új releváns elem", "sent": 0})
    
    # Email összeállítása
    msg = email.message.EmailMessage()
    msg["Subject"] = f"📋 Élelmiszer-jogfigyelő — {len(items)} új releváns változás"
    msg["From"] = config.get("from_email", "")
    msg["To"] = config.get("to_email", "")
    if config.get("cc_email"):
        msg["Cc"] = config["cc_email"]
    
    body = "Élelmiszer-jogfigyelő — AI compliance összefoglaló\n" + "="*50 + "\n\n"
    for it in items:
        body += f"• [{it.get('category','?')}] {it['title']}\n"
        if it.get("impact_summary"):
            body += f"  📝 {it['impact_summary'][:200]}\n"
        if it.get("action_required"):
            body += f"  ⚡ {it['action_required'][:200]}\n"
        if it.get("deadline"):
            body += f"  ⏰ Határidő: {it['deadline']}\n"
        if it.get("url"):
            body += f"  🔗 {it['url']}\n"
        body += "\n"
    body += "—\nÉlelmiszer-jogfigyelő AI rendszer"
    
    msg.set_content(body)
    
    # Küldés — több címzett (vesszővel elválasztva)
    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["smtp_user"], config.get("smtp_pass", ""))
            recipients = [e.strip() for e in config["to_email"].split(",") if e.strip()]
            if config.get("cc_email"):
                recipients += [e.strip() for e in config["cc_email"].split(",") if e.strip()]
            server.send_message(msg, from_addr=config["from_email"], to_addrs=recipients)
        
        db.mark_notified_batch([it["id"] for it in items])
        return jsonify({"message": f"✅ {len(items)} email elküldve {len(recipients)} címre", "sent": len(items)})
    except Exception as e:
        return jsonify({"error": str(e), "sent": 0}), 500


@app.route("/api/test-email", methods=["POST"])
def api_test_email():
    """Teszt email — SMTP kapcsolat ellenőrzése"""
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized — add meg az admin jelszót"}), 401
    config = db.get_email_config()
    if not config or not config.get("smtp_host"):
        return jsonify({"error": "Nincs SMTP konfigurálva"}), 400
    import smtplib, email.message
    msg = email.message.EmailMessage()
    msg["Subject"] = "🧪 Teszt — Élelmiszer-jogfigyelő"
    msg["From"] = config.get("from_email", config.get("smtp_user", ""))
    msg["To"] = config.get("to_email", "")
    if config.get("cc_email"):
        msg["Cc"] = config["cc_email"]
    msg.set_content("Ez egy teszt email. SMTP OK ✅\n\n— Élelmiszer-jogfigyelő")
    try:
        recipients = [e.strip() for e in config["to_email"].split(",") if e.strip()]
        if config.get("cc_email"):
            recipients += [e.strip() for e in config["cc_email"].split(",") if e.strip()]
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["smtp_user"], config.get("smtp_pass", ""))
            server.send_message(msg, from_addr=config["from_email"], to_addrs=recipients)
        return jsonify({"message": f"✅ Teszt email elküldve {len(recipients)} címre", "sent": 1})
    except smtplib.SMTPAuthenticationError:
        return jsonify({"error": "SMTP hitelesítés sikertelen — ellenőrizd a felhasználónevet és jelszót"}), 500
    except smtplib.SMTPException as e:
        return jsonify({"error": f"SMTP hiba: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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