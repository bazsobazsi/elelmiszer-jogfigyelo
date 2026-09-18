import json
import os
import sys
import logging

from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def require_auth():
    auth = request.headers.get("Authorization", "")
    if ADMIN_PASSWORD and not auth.startswith("Bearer "):
        return False
    token = auth.replace("Bearer ", "", 1) if auth else ""
    return (not ADMIN_PASSWORD) or (token == ADMIN_PASSWORD)

def require_auth_post():
    if not ADMIN_PASSWORD:
        return True
    data = request.get_json(silent=True) or {}
    pw = data.get("admin_password", "") or request.headers.get("X-Admin-Key", "")
    return pw == ADMIN_PASSWORD

# DB init
if not os.path.exists(db.DB_PATH):
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "db.py")])

# Auto-seed
seed_lock = os.path.join(db.DB_DIR, ".seeded")
if not os.path.exists(seed_lock):
    seed_path = os.path.join(os.path.dirname(__file__), "seed_data.json")
    if os.path.exists(seed_path):
        try:
            import subprocess as _sub, sys as _sys
            r = _sub.run([_sys.executable, os.path.join(os.path.dirname(__file__), "seed.py")],
                        capture_output=True, text=True, timeout=30)
            print("✅ Auto-seed: seed_data.json betöltve" if r.returncode == 0 else f"⚠️  Auto-seed hiba: {r.stderr[-200:]}")
            open(seed_lock, "w").close()
        except Exception as e:
            print(f"⚠️  Auto-seed exception: {e}")

# ── HTML ──
INDEX_HTML = """<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🍽️ Élelmiszer-jogfigyelő</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;padding:16px}
.header{border-bottom:1px solid #1a1a2e;padding-bottom:12px;margin-bottom:16px}
.header h1{font-size:1.4rem;color:#fff}
.header .sub{font-size:0.85rem;color:#888;margin-top:4px}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.stat-box{background:#12121a;border:1px solid #1a1a2e;border-radius:8px;padding:12px 16px;flex:1;min-width:100px;text-align:center}
.stat-box .num{font-size:1.6rem;font-weight:700;color:#4fc3f7}
.stat-box .label{font-size:0.78rem;color:#888;margin-top:4px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.filters select,.filters input{background:#12121a;border:1px solid #2a2a3e;color:#e0e0e0;padding:8px 12px;border-radius:6px;font-size:0.85rem}
.filters button{background:#4fc3f7;color:#0a0a0f;border:none;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer}
.card{background:#12121a;border:1px solid #1a1a2e;border-radius:10px;padding:14px;margin-bottom:10px}
.card .source{font-size:0.75rem;color:#666;text-transform:uppercase}
.card .title{font-size:1rem;font-weight:600;color:#fff;margin:4px 0}
.card .meta{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.tag{background:#1a1a2e;border-radius:4px;padding:2px 8px;font-size:0.75rem;color:#aaa}
.nav{display:flex;gap:6px}
.nav-btn{background:#1a1a2e;border:1px solid #2a2a3e;color:#888;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:0.82rem}
.nav-btn.active{background:#4fc3f7;color:#0a0a0f;border-color:#4fc3f7}
.tag.red{background:#2e1a1a;color:#f77}
.tag.yellow{background:#2e2a1a;color:#ff7}
.tag.blue{background:#1a1a2e;color:#77f}
.tag.purple{background:#2e1a3e;color:#c77}
.tag.green{background:#1a2e1a;color:#7f7}
.empty{text-align:center;padding:40px;color:#666}
.error-msg{background:#2e1a1a;border:1px solid #5c2a2a;border-radius:8px;padding:12px;color:#f77;margin-bottom:12px}
.log-table{width:100%;border-collapse:collapse;font-size:0.82rem}
.log-table th{text-align:left;color:#888;padding:6px 4px;border-bottom:1px solid #2a2a3e}
.log-table td{padding:6px 4px;border-bottom:1px solid #1a1a2e;color:#ccc}
.recip-text{color:#4fc3f7;font-size:0.78rem;padding:3px 0}
.btn-primary{background:#4fc3f7;color:#0a0a0f;border:none;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer}
.btn-secondary{background:#2a2a3e;color:#e0e0e0;border:none;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer}
.form-status{font-size:0.82rem;color:#4fc3f7;margin-top:8px}
@media(max-width:600px){.stat-box{min-width:calc(50% - 4px)}.filters select{width:100%}}
</style>
</head>
<body>

<div class="header">
  <div style="display:flex;justify-content:space-between;align-items:center">
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
  <div id="error" style="display:none" class="error-msg"></div>
  <div class="stats" id="stats">
    <div class="stat-box"><div class="num" id="stat-total">-</div><div class="label">Összes item</div></div>
    <div class="stat-box"><div class="num" id="stat-relevant">-</div><div class="label">Releváns</div></div>
    <div class="stat-box"><div class="num" id="stat-sources">-</div><div class="label">Források</div></div>
  </div>
  <div class="filters" id="filters">
    <select id="filter-source" onchange="loadItems()"><option value="">Minden forrás</option></select>
    <select id="filter-category" onchange="loadItems()"><option value="">Minden kategória</option></select>
    <select id="filter-relevant" onchange="loadItems()"><option value="">Relevancia szerint</option><option value="1">Csak releváns</option><option value="0">Csak nem releváns</option></select>
  </div>
  <div id="items"></div>
</div>

<div id="page-settings" style="display:none">
  <h2 style="margin-bottom:12px">⚙️ Rendszer beállítások</h2>

  <!-- Admin jelszó (ha be van állítva) -->
  <div id="admin-section" class="card" style="margin-bottom:12px">
    <div style="display:flex;gap:8px;align-items:center">
      <input id="admin_pass" type="password" class="" style="flex:1;background:#1a1a2e;border:1px solid #2a2a3e;color:#e0e0e0;padding:8px;border-radius:6px;font-size:0.85rem" placeholder="Admin jelszó a megtekintéshez">
      <button class="btn-secondary" onclick="unlockSettings()">🔓 Feloldás</button>
    </div>
    <div id="admin-status" class="form-status"></div>
  </div>

  <!-- Feliratkozók kezelése -->
<div id="subscriber-section" class="card" style="margin-bottom:12px;display:none">
  <h3 style="font-size:0.95rem;margin-bottom:8px">📧 Feliratkozott email címek</h3>
  <div style="display:flex;gap:6px;margin-bottom:8px">
    <input id="sub-email" type="email" style="flex:1;background:#1a1a2e;border:1px solid #2a2a3e;color:#e0e0e0;padding:8px;border-radius:6px;font-size:0.85rem" placeholder="email@pelda.hu">
    <button class="btn-primary" onclick="addSubscriber()">➕ Hozzáad</button>
  </div>
  <div id="subscriber-list" style="color:#666;font-size:0.82rem"></div>
  <div id="sub-status" class="form-status"></div>
</div>

  <!-- Crawler vezérlés -->
  <div class="card" style="margin-bottom:12px">
    <h3 style="font-size:0.95rem;margin-bottom:8px">🔄 Crawler vezérlés</h3>
    <button class="btn-primary" onclick="runCrawlers()">▶️ Crawler-ek futtatása</button>
    <div id="crawl-status" class="form-status"></div>
  </div>

  <!-- Küldési előzmények -->
  <div class="card">
    <h3 style="font-size:0.95rem;margin-bottom:8px">📋 Küldési előzmények</h3>
    <div id="send-log">
      <div style="color:#666;padding:12px;text-align:center">⏳ Betöltés...</div>
    </div>
  </div>
</div>

<script>
async function loadItems() {
  const source = document.getElementById('filter-source').value;
  const category = document.getElementById('filter-category').value;
  const relevant = document.getElementById('filter-relevant').value;
  try {
    const res = await fetch('/api/items?' + new URLSearchParams({source,category,relevant}));
    if (!res.ok) throw Error(res.status);
    const data = await res.json();
    if (!Array.isArray(data)) throw Error('nem lista');
    renderItems(data);
  } catch(e) {
    document.getElementById('error').style.display='';
    document.getElementById('error').textContent = 'Hiba: ' + e.message;
  }
}

function renderItems(items) {
  const el = document.getElementById('items');
  if (!items.length) { el.innerHTML = '<div class="empty">📭 Nincs megjeleníthető elem</div>'; return; }
  let html = '';
  for (const it of items) {
    const cat = it.category || 'egyéb';
    const src = it.source || '?';
    const rel = it.relevant ? '<span class="tag green">Releváns</span>' : '';
    const catMap = {'jogszabaly': 'blue', 'jogszabaly_modositas': 'yellow', 'GMP_utmutato': 'purple', 'ertesito': 'green', 'iranyelv': 'blue'};
    const catCls = catMap[cat] || '';
    const catTag = `<span class="tag${catCls?' '+catCls:''}">${cat}</span>`;
    html += '<div class="card">';
    html += `<div class="source">${src}</div>`;
    html += `<div class="title">${esc(it.title)}</div>`;
    html += `<div class="meta">${catTag} ${rel}</div>`;
    if (it.impact_summary) html += `<div class="summary" style="font-size:0.85rem;color:#bbb;line-height:1.4">${esc(it.impact_summary.slice(0,200))}</div>`;
    if (it.action_required) html += `<div class="actions" style="font-size:0.82rem;color:#4fc3f7;margin-top:6px">⚡ ${esc(it.action_required.slice(0,150))}</div>`;
    if (it.deadline) html += `<div class="deadline" style="font-size:0.8rem;color:#ff7;margin-top:4px">⏰ Határidő: ${it.deadline}</div>`;
    if (it.url) html += `<a class="link" style="display:inline-block;margin-top:6px;font-size:0.8rem;color:#4fc3f7;text-decoration:none" href="${it.url}" target="_blank">🔗 Forrás</a>`;
    html += '</div>';
  }
  el.innerHTML = html;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s||''; return d.innerHTML; }

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw Error(res.status);
    const data = await res.json();
    document.getElementById('stat-total').textContent = data.total_items || '0';
    document.getElementById('stat-relevant').textContent = data.relevant_count || '0';
    document.getElementById('stat-sources').textContent = data.sources || '0';
  } catch(e) {
    document.getElementById('error').style.display='';
    document.getElementById('error').textContent = 'Statisztika hiba: ' + e.message;
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
    (data.sources||[]).forEach(s => { sf.innerHTML += `<option value="${s}"${s===sval?' selected':''}>${s}</option>`; });
    cf.innerHTML = '<option value="">Minden kategória</option>';
    (data.categories||[]).forEach(c => { cf.innerHTML += `<option value="${c}"${c===cval?' selected':''}>${c}</option>`; });
  } catch(e) {}
}

// ── Settings ──
let settingsUnlocked = false;

function showTab(name) {
  document.getElementById('page-dashboard').style.display = name === 'dashboard' ? '' : 'none';
  document.getElementById('page-settings').style.display = name === 'settings' ? '' : 'none';
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + (name === 'dashboard' ? 'dash' : 'set')).classList.add('active');
  if (name === 'settings') { loadSubscribers(); loadSendLog(); }
}

function unlockSettings() {
  const pw = document.getElementById('admin_pass').value;
  if (!pw) { document.getElementById('admin-status').textContent = 'Add meg az admin jelszót'; return; }
  fetch('/api/subscribers', {headers:{'Authorization':'Bearer '+pw}})
    .then(r => { if(r.ok) { settingsUnlocked = true; document.getElementById('admin-status').textContent = '✅ Feloldva'; loadSubscribers(); loadSendLog(); }
      else { document.getElementById('admin-status').textContent = '❌ Rossz jelszó'; } })
    .catch(e => { document.getElementById('admin-status').textContent = '❌ Hiba: '+e.message; });
}

function getAdminPass() { return document.getElementById('admin_pass') ? document.getElementById('admin_pass').value : ''; }

async function loadSubscribers() {
  const pw = getAdminPass();
  if (!pw) { document.getElementById('subscriber-section').style.display='none'; return; }
  try {
    const res = await fetch('/api/subscribers', {headers:{'Authorization':'Bearer '+pw}});
    if (!res.ok) { document.getElementById('subscriber-section').style.display='none'; return; }
    const data = await res.json();
    document.getElementById('subscriber-section').style.display='';
    if (!data.length) { document.getElementById('subscriber-list').innerHTML = '<div style="color:#666;padding:8px">📭 Még nincs feliratkozó</div>'; return; }
    let html = '';
    for (const s of data) {
      html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #1a1a2e">`;
      html += `<span style="color:#ccc">📧 ${esc(s.email)}${s.name ? ' ('+esc(s.name)+')' : ''} <span style="color:#666;font-size:0.78rem">(${s.subscribed_at})</span></span>`;
      html += `<button class="btn-secondary" style="padding:2px 8px;font-size:0.78rem" onclick="removeSubscriber('${esc(s.email)}')">✕</button>`;
      html += `</div>`;
    }
    document.getElementById('subscriber-list').innerHTML = html;
  } catch(e) { document.getElementById('subscriber-section').style.display='none'; }
}

async function addSubscriber() {
  const email = document.getElementById('sub-email').value.trim();
  if (!email) { document.getElementById('sub-status').textContent = 'Add meg az email címet'; return; }
  const pw = getAdminPass();
  try {
    const res = await fetch('/api/subscribers', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email, admin_password:pw})});
    const r = await res.json();
    if (r.status === 'ok') { document.getElementById('sub-email').value = ''; document.getElementById('sub-status').textContent = '✅ ' + (r.message || 'Felvéve'); loadSubscribers(); }
    else { document.getElementById('sub-status').textContent = '❌ ' + (r.error || 'Hiba'); }
  } catch(e) { document.getElementById('sub-status').textContent = '❌ Hálózati hiba'; }
}

async function removeSubscriber(email) {
  if (!confirm('Törlöd: ' + email + '?')) return;
  const pw = getAdminPass();
  try {
    const res = await fetch('/api/subscribers', {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email, admin_password:pw})});
    const r = await res.json();
    document.getElementById('sub-status').textContent = r.status === 'ok' ? '✅ Törölve' : '❌ ' + (r.error || 'Hiba');
    loadSubscribers();
  } catch(e) { document.getElementById('sub-status').textContent = '❌ Hálózati hiba'; }
}

async function loadSendLog() {
  const pw = getAdminPass();
  try {
    const res = await fetch('/api/send-log', {headers:{Authorization:'Bearer '+pw}});
    if (!res.ok) { document.getElementById('send-log').innerHTML = '<div style="color:#666;padding:12px;text-align:center">🔒 Feloldás szükséges</div>'; return; }
    const data = await res.json();
    if (!data.length) {
      document.getElementById('send-log').innerHTML = '<div style="color:#666;padding:12px;text-align:center">📭 Még nem történt email küldés</div>';
      return;
    }
    let html = '<table class="log-table"><tr><th>Dátum</th><th>Címzett</th><th>Itemek</th><th>Státusz</th></tr>';
    for (const e of data) {
      const cls = e.status === 'ok' ? 'green' : 'red';
      html += `<tr><td>${e.sent_at||'?'}</td><td><div class="recip-text">${esc(e.recipients)}</div></td><td>${e.item_count}</td><td><span class="tag ${cls}">${e.status}</span></td></tr>`;
    }
    html += '</table>';
    document.getElementById('send-log').innerHTML = html;
  } catch(e) { document.getElementById('send-log').innerHTML = '<div style="color:#f77;padding:12px;text-align:center">❌ Hiba a log betöltésekor</div>'; }
}

async function runCrawlers() {
  document.getElementById('crawl-status').textContent = '⏳ Crawler-ek futtatása...';
  const pw = getAdminPass();
  const headers = {'Content-Type':'application/json'};
  try {
    const res = await fetch('/api/crawl', {method:'POST', headers, body:JSON.stringify({admin_password:pw})});
    const r = await res.json();
    let errs = [];
    for (const [name, res] of Object.entries(r)) {
      if (res.exit === 0) continue;
      errs.push(name + ': ' + (res.error || res.err || 'exit='+res.exit));
    }
    document.getElementById('crawl-status').textContent = errs.length ? '⚠️ ' + errs.join(' | ') : '✅ Crawler kész. Frissítsd a dashboard-ot!';
  } catch(e) { document.getElementById('crawl-status').textContent = '❌ Hiba: ' + e.message; }
}

loadStats();
loadItems();
loadFilters();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# ── API endpoints ──

@app.route("/api/stats")
def api_stats():
    try:
        return jsonify(db.get_stats())
    except Exception as e:
        log.error(f"Stats error: {e}")
        return jsonify({"total_items": 0, "relevant_count": 0, "sources": 0, "error": str(e)})

@app.route("/api/items")
def api_items():
    try:
        source = request.args.get("source", "")
        category = request.args.get("category", "")
        relevant = request.args.get("relevant", "")
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        items = db.get_items_with_analysis(limit=limit, offset=offset)
        filtered = []
        for item in items:
            if source and item.get("source") != source: continue
            if category and item.get("category") != category: continue
            if relevant == "1" and not item.get("relevant"): continue
            filtered.append(item)
        return jsonify(filtered)
    except Exception as e:
        log.error(f"Items error: {e}")
        return jsonify([]), 500

@app.route("/api/filters")
def api_filters():
    try:
        return jsonify(db.get_filters())
    except Exception as e:
        return jsonify({"sources": [], "categories": []})

@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})

# ── Feliratkozók ──

@app.route("/api/subscribers", methods=["GET"])
def api_get_subscribers():
    if ADMIN_PASSWORD and not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(db.get_subscribers())

@app.route("/api/subscribers", methods=["POST"])
def api_add_subscriber():
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Érvénytelen email"}), 400
    ok, result = db.add_subscriber(email, data.get("name", ""))
    if ok:
        return jsonify({"status": "ok", "message": "Feliratkozva", "id": result})
    return jsonify({"error": "Már létezik" if result is None else str(result)}), 400

@app.route("/api/subscribers", methods=["DELETE"])
def api_remove_subscriber():
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email kötelező"}), 400
    db.remove_subscriber(email)
    return jsonify({"status": "ok"})

# ── Send log ──

@app.route("/api/send-log", methods=["GET"])
def api_get_send_log():
    if ADMIN_PASSWORD and not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(db.get_send_log())
    except Exception as e:
        return jsonify([])

@app.route("/api/send-log", methods=["POST"])
def api_post_send_log():
    """Hermes cron hívja, hogy rögzítse a kiküldött emailt"""
    data = request.get_json(silent=True) or {}
    try:
        db.add_send_log(
            recipients=data.get("recipients", ""),
            subject=data.get("subject", ""),
            item_count=data.get("item_count", 0),
            item_ids=data.get("item_ids", []),
            status=data.get("status", "ok"),
            error=data.get("error", ""),
        )
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Digest & send (Hermes cron vagy curl hívja) ──

@app.route("/api/digest-and-send", methods=["POST"])
def api_digest_and_send():
    """
    Hermes cron hívja: összeszedi az új releváns itemeket,
    elküldi SMTP-n keresztül (env vars), logolja az eredményt.
    SMTP beállítások környezeti változókból:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO, EMAIL_CC
    """
    if ADMIN_PASSWORD and not require_auth_post():
        return jsonify({"error": "Unauthorized"}), 401

    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_email = os.environ.get("EMAIL_FROM", "")

    if not smtp_host or not from_email:
        return jsonify({"error": "SMTP nincs konfigurálva (SMTP_HOST, EMAIL_FROM)", "sent": 0}), 400

    subs = db.get_subscribers()
    if not subs:
        return jsonify({"message": "Nincs feliratkozó", "sent": 0})

    items = db.get_unnotified_items()
    if not items:
        return jsonify({"message": "Nincs új releváns elem", "sent": 0})

    import smtplib, email.message

    recipients = [s["email"] for s in subs]
    to_header = ", ".join(recipients)

    body = "Élelmiszer-jogfigyelő — AI compliance összefoglaló\n" + "="*50 + "\n\n"
    for it in items:
        body += f"• [{it.get('category','?')}] {it['title']}\n"
        if it.get("impact_summary"): body += f"  📝 {it['impact_summary'][:200]}\n"
        if it.get("action_required"): body += f"  ⚡ {it['action_required'][:200]}\n"
        if it.get("deadline"): body += f"  ⏰ Határidő: {it['deadline']}\n"
        if it.get("url"): body += f"  🔗 {it['url']}\n"
        body += "\n"
    body += "—\nÉlelmiszer-jogfigyelő AI rendszer"

    msg = email.message.EmailMessage()
    msg["Subject"] = f"📋 Élelmiszer-jogfigyelő — {len(items)} új releváns változás"
    msg["From"] = from_email
    msg["To"] = to_header
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg, from_addr=from_email, to_addrs=recipients)

        # Mark notified
        item_ids = [it["id"] for it in items]
        db.mark_notified_raw(item_ids)

        # Log
        db.add_send_log(
            recipients=to_email + (f" (CC: {cc_email})" if cc_email else ""),
            subject=f"{len(items)} új releváns változás",
            item_count=len(items),
            item_ids=item_ids,
            status="ok",
        )
        return jsonify({"message": f"✅ {len(items)} email elküldve {len(recipients)} címre", "sent": len(items)})
    except smtplib.SMTPAuthenticationError:
        err = "SMTP hitelesítés sikertelen"
        db.add_send_log(recipients=to_email, subject="Hiba", item_count=len(items), item_ids=[it["id"] for it in items], status="error", error=err)
        return jsonify({"error": err, "sent": 0}), 500
    except smtplib.SMTPException as e:
        db.add_send_log(recipients=to_email, subject="Hiba", item_count=len(items), item_ids=[it["id"] for it in items], status="error", error=str(e))
        return jsonify({"error": f"SMTP hiba: {e}", "sent": 0}), 500
    except Exception as e:
        db.add_send_log(recipients=to_email, subject="Hiba", item_count=len(items), item_ids=[it["id"] for it in items], status="error", error=str(e))
        return jsonify({"error": str(e), "sent": 0}), 500

# ── Crawl ──

@app.route("/api/crawl", methods=["POST"])
def api_crawl():
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
            log.error(f"Crawl {name}: {e}")
            results[name] = {"error": str(e)}
    try:
        db.init_db()
    except Exception as e:
        log.error(f"DB init after crawl: {e}")
    return jsonify(results)

@app.route("/api/daily")
def api_daily():
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