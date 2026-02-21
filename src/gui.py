"""
Illumio PCE Monitor — Flask Web GUI.
Optional dependency: pip install flask

Features full parity with CLI:
  Dashboard, Rules (add event/traffic/bandwidth, delete), Settings, Actions (Run, Debug, Test Alert, Best Practices).
"""
import re
import os
import sys
import io
import json
import datetime
import threading
import logging

try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

from src.config import ConfigManager
from src.i18n import t
from src import __version__

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


def _capture_stdout(func):
    """Run func, capture its stdout, strip ANSI, return as string."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        func()
    except Exception as e:
        buf.write(f"\nError: {e}\n")
    finally:
        sys.stdout = old
    return _strip_ansi(buf.getvalue())


# ═══════════════════════════════════════════════════════════════════════════════
# Event Catalog (mirrors settings.py)
# ═══════════════════════════════════════════════════════════════════════════════
FULL_EVENT_CATALOG = {
    "Agent Health": {
        "system_task.agent_missed_heartbeats_check": "Missed Heartbeats",
        "system_task.agent_offline_check": "Agent Offline",
        "lost_agent.found": "Lost Agent Found",
        "agent.service_not_available": "Agent Service Not Available",
        "agent.goodbye": "Agent Goodbye"
    },
    "Agent Security": {
        "agent.tampering": "Agent Tampering",
        "agent.suspend": "Agent Suspended",
        "agent.clone_detected": "Clone Detected",
        "agent.activate": "Agent Activated",
        "agent.deactivate": "Agent Deactivated"
    },
    "User Access": {
        "user.login_failed": "Login Failed",
        "user.sign_in": "User Sign In",
        "user.csrf_validation_failed": "CSRF Validation Failed"
    },
    "Auth & API": {
        "request.authentication_failed": "API Auth Failed",
        "request.authorization_failed": "API Auth Denied",
        "api_key.create": "API Key Created",
        "api_key.delete": "API Key Deleted"
    },
    "Policy": {
        "rule_set.delete": "Ruleset Deleted",
        "rule_set.create": "Ruleset Created",
        "rule_set.update": "Ruleset Updated",
        "sec_rule.create": "Rule Created",
        "sec_rule.delete": "Rule Deleted",
        "sec_policy.create": "Policy Provisioned"
    },
    "Workloads": {
        "workload.create": "Workload Created",
        "workload.delete": "Workload Deleted"
    },
    "System": {
        "pce.application_started": "PCE Started",
        "cluster.update": "Cluster Updated"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# Flask Application Factory
# ═══════════════════════════════════════════════════════════════════════════════

def _create_app(cm: ConfigManager) -> 'Flask':
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False

    # ─── Frontend SPA ─────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return _SPA_HTML

    # ─── API: Status ──────────────────────────────────────────────────────
    @app.route('/api/status')
    def api_status():
        cm.load()
        return jsonify({
            "version": __version__,
            "api_url": cm.config['api']['url'],
            "rules_count": len(cm.config['rules']),
            "health_check": cm.config['settings'].get('enable_health_check', True),
            "language": cm.config.get('settings', {}).get('language', 'en')
        })

    # ─── API: Event Catalog ───────────────────────────────────────────────
    @app.route('/api/event-catalog')
    def api_event_catalog():
        return jsonify(FULL_EVENT_CATALOG)

    # ─── API: Rules CRUD ──────────────────────────────────────────────────
    @app.route('/api/rules')
    def api_rules():
        cm.load()
        rules = []
        for i, r in enumerate(cm.config['rules']):
            rules.append({"index": i, **r})
        return jsonify(rules)

    @app.route('/api/rules/event', methods=['POST'])
    def api_add_event_rule():
        d = request.json
        cm.add_or_update_rule({
            "id": int(datetime.datetime.now().timestamp()),
            "type": "event",
            "name": d.get('name', ''),
            "filter_key": "event_type",
            "filter_value": d.get('filter_value', ''),
            "desc": d.get('name', ''),
            "rec": "Check Logs",
            "threshold_type": d.get('threshold_type', 'immediate'),
            "threshold_count": int(d.get('threshold_count', 1)),
            "threshold_window": int(d.get('threshold_window', 10)),
            "cooldown_minutes": int(d.get('cooldown_minutes', 10))
        })
        if d.get('enable_health_check') is not None:
            cm.config['settings']['enable_health_check'] = bool(d['enable_health_check'])
            cm.save()
        return jsonify({"ok": True})

    @app.route('/api/rules/traffic', methods=['POST'])
    def api_add_traffic_rule():
        d = request.json
        src = (d.get('src') or '').strip()
        dst = (d.get('dst') or '').strip()
        src_label, src_ip = (src, None) if src and '=' in src else (None, src or None)
        dst_label, dst_ip = (dst, None) if dst and '=' in dst else (None, dst or None)
        ex_src = (d.get('ex_src') or '').strip()
        ex_dst = (d.get('ex_dst') or '').strip()
        ex_src_label, ex_src_ip = (ex_src, None) if ex_src and '=' in ex_src else (None, ex_src or None)
        ex_dst_label, ex_dst_ip = (ex_dst, None) if ex_dst and '=' in ex_dst else (None, ex_dst or None)
        port = d.get('port')
        if port:
            try: port = int(port)
            except (ValueError, TypeError): port = None
        ex_port = d.get('ex_port')
        if ex_port:
            try: ex_port = int(ex_port)
            except (ValueError, TypeError): ex_port = None
        proto = d.get('proto')
        if proto:
            try: proto = int(proto)
            except (ValueError, TypeError): proto = None

        cm.add_or_update_rule({
            "id": int(datetime.datetime.now().timestamp()),
            "type": "traffic",
            "name": d.get('name', ''),
            "pd": int(d.get('pd', 2)),
            "port": port, "proto": proto,
            "src_label": src_label, "dst_label": dst_label,
            "src_ip_in": src_ip, "dst_ip_in": dst_ip,
            "ex_port": ex_port,
            "ex_src_label": ex_src_label, "ex_dst_label": ex_dst_label,
            "ex_src_ip": ex_src_ip, "ex_dst_ip": ex_dst_ip,
            "desc": d.get('name', ''), "rec": "Check Policy",
            "threshold_type": "count",
            "threshold_count": int(d.get('threshold_count', 10)),
            "threshold_window": int(d.get('threshold_window', 10)),
            "cooldown_minutes": int(d.get('cooldown_minutes', 10))
        })
        return jsonify({"ok": True})

    @app.route('/api/rules/bandwidth', methods=['POST'])
    def api_add_bw_rule():
        d = request.json
        src = (d.get('src') or '').strip()
        dst = (d.get('dst') or '').strip()
        src_label, src_ip = (src, None) if src and '=' in src else (None, src or None)
        dst_label, dst_ip = (dst, None) if dst and '=' in dst else (None, dst or None)
        port = d.get('port')
        if port:
            try: port = int(port)
            except (ValueError, TypeError): port = None

        cm.add_or_update_rule({
            "id": int(datetime.datetime.now().timestamp()),
            "type": d.get('rule_type', 'bandwidth'),
            "name": d.get('name', ''),
            "pd": int(d.get('pd', -1)),
            "port": port, "proto": None,
            "src_label": src_label, "dst_label": dst_label,
            "src_ip_in": src_ip, "dst_ip_in": dst_ip,
            "desc": d.get('name', ''), "rec": "Check Logs",
            "threshold_type": "count",
            "threshold_count": float(d.get('threshold_count', 100)),
            "threshold_window": int(d.get('threshold_window', 10)),
            "cooldown_minutes": int(d.get('cooldown_minutes', 30))
        })
        return jsonify({"ok": True})

    @app.route('/api/rules/<int:idx>')
    def api_get_rule(idx):
        cm.load()
        if 0 <= idx < len(cm.config['rules']):
            return jsonify({"index": idx, **cm.config['rules'][idx]})
        return jsonify({"error": "not found"}), 404

    @app.route('/api/rules/<int:idx>', methods=['PUT'])
    def api_update_rule(idx):
        d = request.json
        if 0 <= idx < len(cm.config['rules']):
            old = cm.config['rules'][idx]
            old.update(d)
            # Re-parse label/ip fields for traffic and bw/vol
            for prefix in ('src', 'dst', 'ex_src', 'ex_dst'):
                raw = d.get(prefix, '')
                if raw is not None:
                    raw = str(raw).strip()
                    if raw and '=' in raw:
                        old[prefix + '_label'] = raw
                        old[prefix + '_ip_in' if 'ex_' not in prefix else prefix + '_ip'] = None
                    else:
                        old[prefix + '_label'] = None
                        if 'ex_' in prefix:
                            old[prefix + '_ip'] = raw or None
                        else:
                            old[prefix + '_ip_in'] = raw or None
            # Cast numeric fields
            for k in ('port', 'ex_port', 'proto', 'threshold_count', 'threshold_window', 'cooldown_minutes', 'pd'):
                if k in old and old[k] is not None:
                    try: old[k] = int(old[k]) if k != 'threshold_count' else float(old[k])
                    except (ValueError, TypeError): pass
            cm.save()
            return jsonify({"ok": True})
        return jsonify({"error": "not found"}), 404

    @app.route('/api/rules/<int:idx>', methods=['DELETE'])
    def api_delete_rule(idx):
        cm.remove_rules_by_index([idx])
        return jsonify({"ok": True})

    # ─── API: Settings ────────────────────────────────────────────────────
    @app.route('/api/settings')
    def api_get_settings():
        cm.load()
        return jsonify({
            "api": cm.config['api'],
            "email": cm.config['email'],
            "smtp": cm.config.get('smtp', {}),
            "alerts": cm.config.get('alerts', {}),
            "settings": cm.config.get('settings', {})
        })

    @app.route('/api/settings', methods=['POST'])
    def api_save_settings():
        d = request.json
        if 'api' in d:
            for k in ('url', 'org_id', 'key', 'secret', 'verify_ssl'):
                if k in d['api']:
                    cm.config['api'][k] = d['api'][k]
        if 'email' in d:
            if 'sender' in d['email']:
                cm.config['email']['sender'] = d['email']['sender']
            if 'recipients' in d['email']:
                cm.config['email']['recipients'] = d['email']['recipients']
        if 'smtp' in d:
            cm.config.setdefault('smtp', {}).update(d['smtp'])
        if 'alerts' in d:
            cm.config.setdefault('alerts', {}).update(d['alerts'])
        if 'settings' in d:
            cm.config.setdefault('settings', {}).update(d['settings'])
        cm.save()
        return jsonify({"ok": True})

    # ─── API: Actions ─────────────────────────────────────────────────────
    @app.route('/api/actions/run', methods=['POST'])
    def api_run_once():
        def work():
            from src.api_client import ApiClient
            from src.reporter import Reporter
            from src.analyzer import Analyzer
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_analysis()
            rep.send_alerts()
        output = _capture_stdout(work)
        return jsonify({"ok": True, "output": output})

    @app.route('/api/actions/debug', methods=['POST'])
    def api_debug():
        d = request.json or {}
        mins = int(d.get('mins', 30))
        pd_sel = int(d.get('pd_sel', 3))
        def work():
            from src.api_client import ApiClient
            from src.reporter import Reporter
            from src.analyzer import Analyzer
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_debug_mode(mins=mins, pd_sel=pd_sel)
        output = _capture_stdout(work)
        return jsonify({"ok": True, "output": output})

    @app.route('/api/actions/test-alert', methods=['POST'])
    def api_test_alert():
        def work():
            from src.reporter import Reporter
            Reporter(cm).send_alerts(force_test=True)
        output = _capture_stdout(work)
        return jsonify({"ok": True, "output": output})

    @app.route('/api/actions/best-practices', methods=['POST'])
    def api_best_practices():
        output = _capture_stdout(lambda: cm.load_best_practices())
        return jsonify({"ok": True, "output": output})

    @app.route('/api/actions/test-connection', methods=['POST'])
    def api_test_conn():
        try:
            from src.api_client import ApiClient
            api = ApiClient(cm)
            status, body = api.check_health()
            return jsonify({"ok": status == 200, "status": status, "body": _strip_ansi(str(body)[:500])})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route('/api/shutdown', methods=['POST'])
    def api_shutdown():
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
        else:
            os._exit(0)
        return jsonify({"ok": True})

    return app


# ═══════════════════════════════════════════════════════════════════════════════
# Launch
# ═══════════════════════════════════════════════════════════════════════════════

def launch_gui(cm: ConfigManager = None, host='0.0.0.0', port=5001):
    if not HAS_FLASK:
        print("Flask is not installed. The Web GUI requires Flask.")
        print("Install it with:")
        print("  pip install flask")
        return

    if cm is None:
        cm = ConfigManager()

    app = _create_app(cm)
    print(f"\n  Illumio PCE Monitor — Web GUI")
    print(f"  Open in browser: http://127.0.0.1:{port}")
    print(f"  Press Ctrl+C to stop.\n")

    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    app.run(host=host, port=port, debug=False, use_reloader=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Embedded SPA HTML
# ═══════════════════════════════════════════════════════════════════════════════

_SPA_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Illumio PCE Monitor</title>
<style>
:root {
  --bg: #0f0f1a; --bg2: #1a1a2e; --bg3: #252540;
  --fg: #e0e0f0; --dim: #6c7086; --accent: #7c3aed;
  --accent2: #a78bfa; --success: #34d399; --warn: #fbbf24;
  --danger: #f87171; --border: #2d2d44;
  --radius: 10px; --shadow: 0 4px 24px rgba(0,0,0,.4);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--fg); min-height:100vh; }
a { color:var(--accent2); }

/* Header */
.header { background:linear-gradient(135deg,var(--bg2),var(--bg3)); padding:16px 28px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border); }
.header h1 { font-size:1.3rem; font-weight:700; background:linear-gradient(135deg,var(--accent2),var(--success)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.header .meta { color:var(--dim); font-size:.85rem; }

/* Tabs */
.tabs { display:flex; gap:2px; background:var(--bg2); padding:6px 20px 0; border-bottom:1px solid var(--border); }
.tab { padding:10px 22px; cursor:pointer; border-radius:var(--radius) var(--radius) 0 0; color:var(--dim); font-weight:600; font-size:.9rem; transition:.2s; border:1px solid transparent; border-bottom:none; }
.tab:hover { color:var(--fg); background:var(--bg3); }
.tab.active { color:var(--accent2); background:var(--bg); border-color:var(--border); }

/* Panel */
.panel { display:none; padding:24px; animation:fadeIn .2s; }
.panel.active { display:block; }
@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }

/* Cards */
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin-bottom:20px; }
.card { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:18px; text-align:center; }
.card .label { color:var(--dim); font-size:.8rem; margin-bottom:6px; }
.card .value { font-size:1.8rem; font-weight:700; color:var(--accent2); }
.card .value.ok { color:var(--success); }
.card .value.err { color:var(--danger); }

/* Buttons */
.btn { display:inline-flex; align-items:center; gap:6px; padding:9px 18px; border:none; border-radius:8px; font-size:.88rem; font-weight:600; cursor:pointer; transition:.15s; }
.btn-primary { background:var(--accent); color:#fff; }
.btn-primary:hover { background:var(--accent2); }
.btn-success { background:#059669; color:#fff; }
.btn-success:hover { background:var(--success); color:#000; }
.btn-danger { background:#dc2626; color:#fff; }
.btn-danger:hover { background:var(--danger); }
.btn-warn { background:#d97706; color:#fff; }
.btn-warn:hover { background:var(--warn); color:#000; }
.btn-sm { padding:6px 12px; font-size:.8rem; }
.btn:disabled { opacity:.5; cursor:not-allowed; }

/* Forms */
.form-group { margin-bottom:12px; }
.form-group label { display:block; color:var(--dim); font-size:.82rem; margin-bottom:4px; font-weight:600; }
.form-group input, .form-group select { width:100%; background:var(--bg); border:1px solid var(--border); color:var(--fg); padding:8px 12px; border-radius:6px; font-size:.9rem; }
.form-group input:focus, .form-group select:focus { outline:none; border-color:var(--accent); }
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.form-row-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }

/* Fieldset */
fieldset { border:1px solid var(--border); border-radius:var(--radius); padding:16px; margin-bottom:16px; }
legend { color:var(--accent2); font-weight:700; font-size:.9rem; padding:0 8px; }

/* Table */
.rule-table { width:100%; border-collapse:collapse; margin-top:12px; }
.rule-table th, .rule-table td { text-align:left; padding:10px 14px; border-bottom:1px solid var(--border); font-size:.88rem; }
.rule-table th { color:var(--dim); font-weight:600; background:var(--bg2); }
.rule-table tr:hover td { background:var(--bg3); }

/* Log */
.log-box { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:14px; font-family:'Cascadia Code','Fira Code',monospace; font-size:.82rem; color:var(--fg); max-height:360px; overflow-y:auto; white-space:pre-wrap; word-break:break-all; line-height:1.6; }

/* Actions */
.action-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-bottom:20px; }
.action-card { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:18px; display:flex; flex-direction:column; gap:10px; }
.action-card h3 { font-size:.95rem; color:var(--accent2); }
.action-card p { font-size:.8rem; color:var(--dim); flex:1; }

/* Modal */
.modal-bg { display:none; position:fixed; inset:0; background:rgba(0,0,0,.6); z-index:100; align-items:center; justify-content:center; }
.modal-bg.show { display:flex; }
.modal { background:var(--bg); border:1px solid var(--border); border-radius:14px; padding:24px; width:560px; max-width:95vw; max-height:85vh; overflow-y:auto; box-shadow:var(--shadow); }
.modal h2 { font-size:1.1rem; color:var(--accent2); margin-bottom:16px; }
.modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; }

/* Toolbar */
.toolbar { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; align-items:center; }
.toolbar .spacer { flex:1; }
.badge { background:var(--accent); color:#fff; padding:2px 10px; border-radius:20px; font-size:.78rem; font-weight:700; }

/* Radio group */
.radio-group { display:flex; gap:12px; flex-wrap:wrap; }
.radio-group label { display:flex; align-items:center; gap:4px; color:var(--fg); font-size:.88rem; cursor:pointer; }
.radio-group input[type=radio] { accent-color:var(--accent); }

/* Checkbox */
.chk label { display:flex; align-items:center; gap:6px; color:var(--fg); font-size:.88rem; cursor:pointer; }
.chk input[type=checkbox] { accent-color:var(--accent); }

/* Toast */
.toast { position:fixed; bottom:24px; right:24px; background:var(--success); color:#000; padding:12px 20px; border-radius:8px; font-weight:600; font-size:.88rem; z-index:200; opacity:0; transition:.3s; pointer-events:none; }
.toast.show { opacity:1; }
.toast.err { background:var(--danger); color:#fff; }
</style>
</head>
<body>

<div class="header">
  <h1>◆ Illumio PCE Monitor</h1>
  <div style="display:flex;align-items:center;gap:14px"><span class="meta" id="hdr-meta">Loading...</span><button class="btn btn-danger btn-sm" onclick="stopGui()" title="Stop Web GUI">⏹ Stop</button></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('dashboard')">Dashboard</div>
  <div class="tab" onclick="switchTab('rules')">Rules</div>
  <div class="tab" onclick="switchTab('settings')">Settings</div>
  <div class="tab" onclick="switchTab('actions')">Actions</div>
</div>

<!-- ═══ Dashboard ═══ -->
<div class="panel active" id="p-dashboard">
  <div class="cards">
    <div class="card"><div class="label">API Status</div><div class="value" id="d-api">—</div></div>
    <div class="card"><div class="label">Active Rules</div><div class="value" id="d-rules">—</div></div>
    <div class="card"><div class="label">Health Check</div><div class="value" id="d-health">—</div></div>
    <div class="card"><div class="label">Language</div><div class="value" id="d-lang">—</div></div>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:14px;">
    <button class="btn btn-primary" onclick="testConn()">🔗 Test Connection</button>
    <button class="btn btn-primary" onclick="loadDashboard()">🔄 Refresh</button>
  </div>
  <div class="log-box" id="d-log">[Ready]</div>
</div>

<!-- ═══ Rules ═══ -->
<div class="panel" id="p-rules">
  <div class="toolbar">
    <span style="font-size:1.1rem;font-weight:700;color:var(--accent2)">Rules</span>
    <span class="badge" id="r-badge">0</span>
    <div class="spacer"></div>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-event')">📋 + Event</button>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-traffic')">🚦 + Traffic</button>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-bw')">📊 + BW/Vol</button>
    <button class="btn btn-danger btn-sm" onclick="deleteSelected()">🗑 Delete</button>
  </div>
  <table class="rule-table">
    <thead><tr><th style="width:30px"><input type="checkbox" id="r-chkall" onchange="toggleAll(this)"></th><th>Type</th><th>Name</th><th>Condition</th><th>Filters</th><th style="width:50px">Edit</th></tr></thead>
    <tbody id="r-body"></tbody>
  </table>
</div>

<!-- ═══ Settings ═══ -->
<div class="panel" id="p-settings">
  <div id="s-form"></div>
  <div style="text-align:right;margin-top:16px;">
    <button class="btn btn-success" onclick="saveSettings()">💾 Save All Settings</button>
  </div>
</div>

<!-- ═══ Actions ═══ -->
<div class="panel" id="p-actions">
  <div class="action-grid">
    <div class="action-card"><h3>▶ Run Monitor Once</h3><p>Execute full cycle: Health → Fetch → Analyze → Alert</p><button class="btn btn-primary" onclick="runAction('run')">Run</button></div>
    <div class="action-card"><h3>🔍 Debug Mode</h3><p>Sandbox mode — no alerts, no state updates</p>
      <div class="form-row" style="margin-bottom:8px;">
        <div class="form-group"><label>Window (min)</label><input id="a-debug-mins" value="30"></div>
        <div class="form-group"><label>Policy Dec.</label><select id="a-debug-pd"><option value="1">Blocked</option><option value="2">Allowed</option><option value="3" selected>All</option></select></div>
      </div>
      <button class="btn btn-primary" onclick="runDebug()">Run Debug</button>
    </div>
    <div class="action-card"><h3>📧 Send Test Alert</h3><p>Verify Email / LINE / Webhook delivery</p><button class="btn btn-primary" onclick="runAction('test-alert')">Send</button></div>
    <div class="action-card"><h3>📋 Load Best Practices</h3><p>Replace ALL existing rules with recommended defaults</p><button class="btn btn-danger" onclick="confirmBestPractices()">Load</button></div>
  </div>
  <h3 style="color:var(--accent2);margin-bottom:8px;">Output</h3>
  <div class="log-box" id="a-log"></div>
</div>

<!-- ═══ Modals ═══ -->
<!-- Event -->
<div class="modal-bg" id="m-event"><div class="modal">
  <h2>Add Event Rule</h2>
  <div class="form-group"><label>Category</label><select id="ev-cat" onchange="populateEvents()"><option value="">Select...</option></select></div>
  <div class="form-group"><label>Event Type</label><select id="ev-type"><option value="">Select category first</option></select></div>
  <fieldset><legend>Threshold</legend>
    <div class="form-group"><label>Type</label><div class="radio-group"><label><input type="radio" name="ev-tt" value="immediate" checked> Immediate</label><label><input type="radio" name="ev-tt" value="count"> Cumulative</label></div></div>
    <div class="form-row-3">
      <div class="form-group"><label>Count</label><input id="ev-cnt" type="number" value="5"></div>
      <div class="form-group"><label>Window (min)</label><input id="ev-win" type="number" value="10"></div>
      <div class="form-group"><label>Cooldown (min)</label><input id="ev-cd" type="number" value="10"></div>
    </div>
  </fieldset>
  <div class="chk"><label><input type="checkbox" id="ev-hc" checked> Enable PCE Health Check</label></div>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-event')">Cancel</button><button class="btn btn-success" onclick="saveEvent()">💾 Save</button></div>
</div></div>

<!-- Traffic -->
<div class="modal-bg" id="m-traffic"><div class="modal">
  <h2>Add Traffic Rule</h2>
  <div class="form-group"><label>Rule Name</label><input id="tr-name"></div>
  <fieldset><legend>Policy Decision</legend><div class="radio-group">
    <label><input type="radio" name="tr-pd" value="2" checked> Blocked</label>
    <label><input type="radio" name="tr-pd" value="1"> Potential</label>
    <label><input type="radio" name="tr-pd" value="0"> Allowed</label>
    <label><input type="radio" name="tr-pd" value="-1"> All</label>
  </div></fieldset>
  <fieldset><legend>Filters</legend>
    <div class="form-row"><div class="form-group"><label>Port</label><input id="tr-port" placeholder="e.g. 443"></div><div class="form-group"><label>Protocol</label><select id="tr-proto"><option value="">Both</option><option value="6">TCP</option><option value="17">UDP</option></select></div></div>
    <div class="form-row"><div class="form-group"><label>Source (Label/IP)</label><input id="tr-src" placeholder="e.g. role=Web or 10.0.0.1"></div><div class="form-group"><label>Destination (Label/IP)</label><input id="tr-dst"></div></div>
  </fieldset>
  <fieldset><legend>Excludes (Optional)</legend>
    <div class="form-row-3"><div class="form-group"><label>Port</label><input id="tr-expt"></div><div class="form-group"><label>Source</label><input id="tr-exsrc"></div><div class="form-group"><label>Destination</label><input id="tr-exdst"></div></div>
  </fieldset>
  <fieldset><legend>Threshold</legend>
    <div class="form-row-3"><div class="form-group"><label>Count</label><input id="tr-cnt" type="number" value="10"></div><div class="form-group"><label>Window (min)</label><input id="tr-win" type="number" value="10"></div><div class="form-group"><label>Cooldown (min)</label><input id="tr-cd" type="number" value="10"></div></div>
  </fieldset>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-traffic')">Cancel</button><button class="btn btn-success" onclick="saveTraffic()">💾 Save</button></div>
</div></div>

<!-- BW/Volume -->
<div class="modal-bg" id="m-bw"><div class="modal">
  <h2>Add Bandwidth / Volume Rule</h2>
  <div class="form-group"><label>Rule Name</label><input id="bw-name"></div>
  <fieldset><legend>Metric Type</legend><div class="radio-group">
    <label><input type="radio" name="bw-mt" value="bandwidth" checked> Bandwidth (Mbps, Max)</label>
    <label><input type="radio" name="bw-mt" value="volume"> Volume (MB, Sum)</label>
  </div></fieldset>
  <fieldset><legend>Policy Decision</legend><div class="radio-group">
    <label><input type="radio" name="bw-pd" value="2"> Blocked</label>
    <label><input type="radio" name="bw-pd" value="1"> Potential</label>
    <label><input type="radio" name="bw-pd" value="0"> Allowed</label>
    <label><input type="radio" name="bw-pd" value="-1" checked> All</label>
  </div></fieldset>
  <fieldset><legend>Filters</legend>
    <div class="form-row-3"><div class="form-group"><label>Port</label><input id="bw-port"></div><div class="form-group"><label>Source</label><input id="bw-src"></div><div class="form-group"><label>Destination</label><input id="bw-dst"></div></div>
  </fieldset>
  <fieldset><legend>Threshold</legend>
    <div class="form-row-3"><div class="form-group"><label>Value</label><input id="bw-val" type="number" value="100"></div><div class="form-group"><label>Window (min)</label><input id="bw-win" type="number" value="10"></div><div class="form-group"><label>Cooldown (min)</label><input id="bw-cd" type="number" value="30"></div></div>
  </fieldset>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-bw')">Cancel</button><button class="btn btn-success" onclick="saveBW()">💾 Save</button></div>
</div></div>

<div class="toast" id="toast"></div>

<script>
/* ─── Helpers ─────────────────────────────────────────────────────── */
const $=s=>document.getElementById(s);
const api=async(url,opt)=>{const r=await fetch(url,opt);return r.json()};
const post=(url,body)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const put=(url,body)=>api(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const del=url=>api(url,{method:'DELETE'});
const rv=name=>document.querySelector(`input[name="${name}"]:checked`)?.value;
const setRv=(name,val)=>{const r=document.querySelector(`input[name="${name}"][value="${val}"]`);if(r)r.checked=true};
let _editIdx=null; // null = add mode, number = edit mode

function toast(msg,err){const t=$('toast');t.textContent=msg;t.className='toast'+(err?' err':'')+' show';setTimeout(()=>t.className='toast',3000)}
function dlog(msg){const l=$('d-log');l.textContent+='\n['+new Date().toLocaleTimeString()+'] '+msg;l.scrollTop=l.scrollHeight}
function alog(msg){const l=$('a-log');l.textContent+='\n'+msg;l.scrollTop=l.scrollHeight}

/* ─── Tabs ────────────────────────────────────────────────────────── */
function switchTab(id){
  document.querySelectorAll('.tab').forEach((t,i)=>{t.classList.toggle('active',t.textContent.trim().toLowerCase().startsWith(id.slice(0,4)))});
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  $('p-'+id).classList.add('active');
  if(id==='rules') loadRules();
  if(id==='settings') loadSettings();
  if(id==='dashboard') loadDashboard();
}

/* ─── Dashboard ───────────────────────────────────────────────────── */
async function loadDashboard(){
  const d=await api('/api/status');
  $('hdr-meta').textContent=`v${d.version} | ${d.api_url}`;
  $('d-rules').textContent=d.rules_count;
  $('d-health').textContent=d.health_check?'ON':'OFF';
  $('d-lang').textContent=(d.language||'en').toUpperCase();
}
async function testConn(){
  dlog('Testing PCE connection...');
  const r=await post('/api/actions/test-connection',{});
  if(r.ok){$('d-api').textContent='Connected';$('d-api').className='value ok';dlog('✅ Connected (HTTP '+r.status+')')}
  else{$('d-api').textContent='Error';$('d-api').className='value err';dlog('❌ '+( r.error||r.body))}
}

/* ─── Rules ───────────────────────────────────────────────────────── */
let _catalog={};
async function loadRules(){
  const rules=await api('/api/rules');
  $('r-badge').textContent=rules.length;
  const pdm={2:'Blocked',1:'Potential',0:'Allowed','-1':'All'};
  let html='';
  rules.forEach(r=>{
    const typ=r.type.charAt(0).toUpperCase()+r.type.slice(1);
    const unit={volume:' MB',bandwidth:' Mbps',traffic:' conns'}[r.type]||'';
    const cond='> '+r.threshold_count+unit+' (Win:'+r.threshold_window+'m CD:'+(r.cooldown_minutes||r.threshold_window)+'m)';
    let f=[];
    if(r.type==='event') f.push('Event: '+r.filter_value);
    if(r.pd!==undefined&&r.pd!==null) f.push('PD:'+( pdm[r.pd]||r.pd));
    if(r.port) f.push('Port:'+r.port);
    if(r.src_label) f.push('Src:'+r.src_label);if(r.dst_label) f.push('Dst:'+r.dst_label);
    if(r.src_ip_in) f.push('SrcIP:'+r.src_ip_in);if(r.dst_ip_in) f.push('DstIP:'+r.dst_ip_in);
    html+=`<tr><td><input type="checkbox" class="r-chk" data-idx="${r.index}"></td><td>${typ}</td><td>${r.name}</td><td>${cond}</td><td>${f.join(' | ')||'—'}</td><td><button class="btn btn-primary btn-sm" onclick="editRule(${r.index},'${r.type}')">✏️</button></td></tr>`;
  });
  $('r-body').innerHTML=html||'<tr><td colspan="6" style="color:var(--dim);text-align:center;padding:24px">No rules. Add one above.</td></tr>';
}
function toggleAll(el){document.querySelectorAll('.r-chk').forEach(c=>c.checked=el.checked)}
async function deleteSelected(){
  const ids=[...document.querySelectorAll('.r-chk:checked')].map(c=>parseInt(c.dataset.idx)).sort((a,b)=>b-a);
  if(!ids.length){toast('Select rules first','err');return}
  if(!confirm('Delete '+ids.length+' rule(s)?'))return;
  for(const i of ids) await del('/api/rules/'+i);
  toast('Deleted');loadRules();loadDashboard();
}
function openModal(id,isEdit){_editIdx=isEdit??null;$(id).classList.add('show');if(id==='m-event'&&!Object.keys(_catalog).length)loadCatalog();
  // Update modal title
  const h=$(id).querySelector('h2');
  if(h){const base=h.textContent.replace(/^(Edit|Add) /,'');h.textContent=(_editIdx!==null?'Edit ':'Add ')+base}
}
function closeModal(id){$(id).classList.remove('show');_editIdx=null}
async function loadCatalog(){
  _catalog=await api('/api/event-catalog');
  const sel=$('ev-cat');sel.innerHTML='<option value="">Select...</option>';
  Object.keys(_catalog).forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o)});
}
function populateEvents(){
  const cat=$('ev-cat').value;const sel=$('ev-type');sel.innerHTML='';
  if(!cat||!_catalog[cat]){sel.innerHTML='<option>Select category first</option>';return}
  Object.entries(_catalog[cat]).forEach(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=k+' ('+v+')';sel.appendChild(o)});
}

/* ─── Edit Rule ───────────────────────────────────────────────────── */
async function editRule(idx,type){
  const r=await api('/api/rules/'+idx);
  if(r.error){toast('Rule not found','err');return}
  if(type==='event'){
    await loadCatalog();
    // Find and select category
    for(const[cat,evts] of Object.entries(_catalog)){
      if(r.filter_value in evts){$('ev-cat').value=cat;populateEvents();$('ev-type').value=r.filter_value;break}
    }
    setRv('ev-tt',r.threshold_type||'immediate');
    $('ev-cnt').value=r.threshold_count||5;
    $('ev-win').value=r.threshold_window||10;
    $('ev-cd').value=r.cooldown_minutes||10;
    openModal('m-event',idx);
  } else if(type==='traffic'){
    $('tr-name').value=r.name||'';
    setRv('tr-pd',String(r.pd??2));
    $('tr-port').value=r.port||'';
    $('tr-proto').value=r.proto?String(r.proto):'';
    $('tr-src').value=r.src_label||r.src_ip_in||'';
    $('tr-dst').value=r.dst_label||r.dst_ip_in||'';
    $('tr-expt').value=r.ex_port||'';
    $('tr-exsrc').value=r.ex_src_label||r.ex_src_ip||'';
    $('tr-exdst').value=r.ex_dst_label||r.ex_dst_ip||'';
    $('tr-cnt').value=r.threshold_count||10;
    $('tr-win').value=r.threshold_window||10;
    $('tr-cd').value=r.cooldown_minutes||10;
    openModal('m-traffic',idx);
  } else {
    $('bw-name').value=r.name||'';
    setRv('bw-mt',r.type||'bandwidth');
    setRv('bw-pd',String(r.pd??-1));
    $('bw-port').value=r.port||'';
    $('bw-src').value=r.src_label||r.src_ip_in||'';
    $('bw-dst').value=r.dst_label||r.dst_ip_in||'';
    $('bw-val').value=r.threshold_count||100;
    $('bw-win').value=r.threshold_window||10;
    $('bw-cd').value=r.cooldown_minutes||30;
    openModal('m-bw',idx);
  }
}

async function saveEvent(){
  const cat=$('ev-cat').value,ev=$('ev-type').value;
  if(!cat||!ev){toast('Select category and event','err');return}
  const name=(_catalog[cat]||{})[ev]||ev;
  const data={name,filter_value:ev,threshold_type:rv('ev-tt'),threshold_count:$('ev-cnt').value,threshold_window:$('ev-win').value,cooldown_minutes:$('ev-cd').value,enable_health_check:$('ev-hc').checked};
  if(_editIdx!==null) await put('/api/rules/'+_editIdx,data); else await post('/api/rules/event',data);
  closeModal('m-event');toast('Event rule saved');loadRules();loadDashboard();
}
async function saveTraffic(){
  const name=$('tr-name').value.trim();if(!name){toast('Name required','err');return}
  const data={name,pd:rv('tr-pd'),port:$('tr-port').value,proto:$('tr-proto').value,src:$('tr-src').value,dst:$('tr-dst').value,ex_port:$('tr-expt').value,ex_src:$('tr-exsrc').value,ex_dst:$('tr-exdst').value,threshold_count:$('tr-cnt').value,threshold_window:$('tr-win').value,cooldown_minutes:$('tr-cd').value};
  if(_editIdx!==null) await put('/api/rules/'+_editIdx,data); else await post('/api/rules/traffic',data);
  closeModal('m-traffic');toast('Traffic rule saved');loadRules();loadDashboard();
}
async function saveBW(){
  const name=$('bw-name').value.trim();if(!name){toast('Name required','err');return}
  const data={name,rule_type:rv('bw-mt'),pd:rv('bw-pd'),port:$('bw-port').value,src:$('bw-src').value,dst:$('bw-dst').value,threshold_count:$('bw-val').value,threshold_window:$('bw-win').value,cooldown_minutes:$('bw-cd').value};
  if(_editIdx!==null) await put('/api/rules/'+_editIdx,{...data,type:data.rule_type}); else await post('/api/rules/bandwidth',data);
  closeModal('m-bw');toast('Rule saved');loadRules();loadDashboard();
}

function confirmBestPractices(){
  if(!confirm('⚠️ WARNING: This will DELETE all existing rules and replace them with best practice defaults.\n\nAre you sure you want to continue?')) return;
  if(!confirm('This action cannot be undone. Confirm once more to proceed.')) return;
  runAction('best-practices');
}

/* ─── Settings ────────────────────────────────────────────────────── */
let _settings={};
async function loadSettings(){
  _settings=await api('/api/settings');
  const s=_settings,a=s.api||{},e=s.email||{},sm=s.smtp||{},al=s.alerts||{},st=s.settings||{};
  const active=al.active||[];
  $('s-form').innerHTML=`
  <fieldset><legend>API Connection</legend>
    <div class="form-row"><div class="form-group"><label>URL</label><input id="s-url" value="${a.url||''}"></div><div class="form-group"><label>Org ID</label><input id="s-org" value="${a.org_id||''}"></div></div>
    <div class="form-row"><div class="form-group"><label>API Key</label><input id="s-key" value="${a.key||''}"></div><div class="form-group"><label>API Secret</label><input id="s-sec" type="password" value="${a.secret||''}"></div></div>
    <div class="chk"><label><input type="checkbox" id="s-ssl" ${a.verify_ssl?'checked':''}> Verify SSL</label></div>
  </fieldset>
  <fieldset><legend>Email & SMTP</legend>
    <div class="form-row"><div class="form-group"><label>Sender</label><input id="s-sender" value="${e.sender||''}"></div><div class="form-group"><label>Recipients (comma)</label><input id="s-rcpt" value="${(e.recipients||[]).join(', ')}"></div></div>
    <div class="form-row"><div class="form-group"><label>SMTP Host</label><input id="s-smhost" value="${sm.host||''}"></div><div class="form-group"><label>Port</label><input id="s-smport" value="${sm.port||25}"></div></div>
    <div class="form-row"><div class="form-group"><label>User</label><input id="s-smuser" value="${sm.user||''}"></div><div class="form-group"><label>Password</label><input id="s-smpass" type="password" value="${sm.password||''}"></div></div>
    <div style="display:flex;gap:20px"><div class="chk"><label><input type="checkbox" id="s-tls" ${sm.enable_tls?'checked':''}> STARTTLS</label></div><div class="chk"><label><input type="checkbox" id="s-auth" ${sm.enable_auth?'checked':''}> Auth</label></div></div>
  </fieldset>
  <fieldset><legend>Alert Channels</legend>
    <div style="display:flex;gap:20px;margin-bottom:12px"><div class="chk"><label><input type="checkbox" id="s-amail" ${active.includes('mail')?'checked':''}> 📧 Mail</label></div><div class="chk"><label><input type="checkbox" id="s-aline" ${active.includes('line')?'checked':''}> 📱 LINE</label></div><div class="chk"><label><input type="checkbox" id="s-awh" ${active.includes('webhook')?'checked':''}> 🔗 Webhook</label></div></div>
    <div class="form-row"><div class="form-group"><label>LINE Token</label><input id="s-ltok" value="${al.line_channel_access_token||''}"></div><div class="form-group"><label>LINE Target ID</label><input id="s-ltgt" value="${al.line_target_id||''}"></div></div>
    <div class="form-group"><label>Webhook URL</label><input id="s-whurl" value="${al.webhook_url||''}"></div>
  </fieldset>
  <fieldset><legend>Language</legend><div class="radio-group"><label><input type="radio" name="s-lang" value="en" ${st.language!=='zh_TW'?'checked':''}> English</label><label><input type="radio" name="s-lang" value="zh_TW" ${st.language==='zh_TW'?'checked':''}> 繁體中文</label></div></fieldset>`;
}
async function saveSettings(){
  const active=[];if($('s-amail').checked)active.push('mail');if($('s-aline').checked)active.push('line');if($('s-awh').checked)active.push('webhook');
  await post('/api/settings',{
    api:{url:$('s-url').value,org_id:$('s-org').value,key:$('s-key').value,secret:$('s-sec').value,verify_ssl:$('s-ssl').checked},
    email:{sender:$('s-sender').value,recipients:$('s-rcpt').value.split(',').map(s=>s.trim()).filter(Boolean)},
    smtp:{host:$('s-smhost').value,port:parseInt($('s-smport').value)||25,user:$('s-smuser').value,password:$('s-smpass').value,enable_tls:$('s-tls').checked,enable_auth:$('s-auth').checked},
    alerts:{active,line_channel_access_token:$('s-ltok').value,line_target_id:$('s-ltgt').value,webhook_url:$('s-whurl').value},
    settings:{language:rv('s-lang')}
  });
  toast('Settings saved');
}

/* ─── Actions ─────────────────────────────────────────────────────── */
async function runAction(name){
  $('a-log').textContent='['+new Date().toLocaleTimeString()+'] Running '+name+'...';
  const r=await post('/api/actions/'+name,{});
  alog(r.output||'Done.');
  if(name==='best-practices'){loadRules();loadDashboard()}
  toast('✅ '+name+' completed');
}
async function runDebug(){
  $('a-log').textContent='['+new Date().toLocaleTimeString()+'] Running debug mode...';
  const r=await post('/api/actions/debug',{mins:$('a-debug-mins').value,pd_sel:$('a-debug-pd').value});
  alog(r.output||'Done.');
  toast('✅ Debug completed');
}

/* ─── Init ────────────────────────────────────────────────────────── */
async function stopGui(){
  if(!confirm('Stop the Web GUI server? The browser page will close.')) return;
  try{ await post('/api/shutdown',{}); } catch(e){}
  document.body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:12px"><h1 style="color:var(--accent2)">Web GUI Stopped</h1><p style="color:var(--dim)">You may close this tab. Restart from CLI or use --gui.</p></div>';
}
loadDashboard();
</script>
</body>
</html>'''
