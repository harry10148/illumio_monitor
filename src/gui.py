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
    @app.route('/api/ui_translations')
    def api_ui_translations():
        lang = cm.config.get("settings", {}).get("language", "en")
        from src.i18n import MESSAGES
        ui_dict = {k: v for k, v in MESSAGES.get(lang, MESSAGES["en"]).items() if k.startswith("gui_")}
        return jsonify(ui_dict)

    @app.route('/api/status')
    def api_status():
        cm.load()
        return jsonify({
            "version": __version__,
            "api_url": cm.config['api']['url'],
            "rules_count": len(cm.config['rules']),
            "health_check": cm.config['settings'].get('enable_health_check', True),
            "language": cm.config.get('settings', {}).get('language', 'en'),
            "theme": cm.config.get('settings', {}).get('theme', 'dark')
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

        cm.add_or_update_rule({
            "id": int(datetime.datetime.now().timestamp()),
            "type": d.get('rule_type', 'bandwidth'),
            "name": d.get('name', ''),
            "pd": int(d.get('pd', -1)),
            "port": port, "proto": None,
            "src_label": src_label, "dst_label": dst_label,
            "src_ip_in": src_ip, "dst_ip_in": dst_ip,
            "ex_port": ex_port,
            "ex_src_label": ex_src_label, "ex_dst_label": ex_dst_label,
            "ex_src_ip": ex_src_ip, "ex_dst_ip": ex_dst_ip,
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
            "api": cm.config.get("api", {}),
            "email": cm.config.get("email", {}),
            "smtp": cm.config.get("smtp", {}),
            "alerts": cm.config.get("alerts", {}),
            "settings": cm.config.get("settings", {})
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
            body_text = str(body)
            clean_body = _strip_ansi(body_text)
            return jsonify({"ok": status == 200, "status": status, "body": clean_body[:500]})
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
  --bg: #1a2c32; --bg2: #24393f; --bg3: #2d454c;
  --fg: #F5F5F5; --dim: #989A9B; --accent: #FF5500;
  --accent2: #FFA22F; --success: #299b65; --warn: #FFB74A;
  --danger: #f43f51; --border: #325158;
  --radius: 10px; --shadow: 0 4px 24px rgba(0,0,0,.4);
}
[data-theme="light"] {
  --bg: #F5F5F5; --bg2: #FFFFFF; --bg3: #EAEBEB;
  --fg: #313638; --dim: #6F7274; --accent: #FF5500;
  --accent2: #F97607; --success: #166644; --warn: #FFA22F;
  --danger: #be122f; --border: #D6D7D7;
  --shadow: 0 2px 10px rgba(0,0,0,.05);
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
.btn-primary:hover { background:var(--accent2); color:#1a2c32; }
.btn-success { background:#166644; color:#fff; }
.btn-success:hover { background:var(--success); color:#fff; }
.btn-danger { background:#be122f; color:#fff; }
.btn-danger:hover { background:var(--danger); }
.btn-warn { background:#d97706; color:#fff; }
.btn-warn:hover { background:var(--warn); color:#1a2c32; }
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
  <h1 data-i18n="gui_title">◆ Illumio PCE Monitor</h1>
  <div style="display:flex;align-items:center;gap:14px"><span class="meta" id="hdr-meta">Loading...</span><button class="btn btn-danger btn-sm" onclick="stopGui()" title="Stop Web GUI" data-i18n="gui_stop">⏹ Stop</button></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('dashboard')" data-i18n="gui_tab_dashboard">Dashboard</div>
  <div class="tab" onclick="switchTab('rules')" data-i18n="gui_tab_rules">Rules</div>
  <div class="tab" onclick="switchTab('settings')" data-i18n="gui_tab_settings">Settings</div>
  <div class="tab" onclick="switchTab('actions')" data-i18n="gui_tab_actions">Actions</div>
</div>

<!-- ═══ Dashboard ═══ -->
<div class="panel active" id="p-dashboard">
  <div class="cards">
    <div class="card"><div class="label" data-i18n="gui_api_status">API Status</div><div class="value" id="d-api">—</div></div>
    <div class="card"><div class="label" data-i18n="gui_active_rules">Active Rules</div><div class="value" id="d-rules">—</div></div>
    <div class="card"><div class="label" data-i18n="gui_health_check">Health Check</div><div class="value" id="d-health">—</div></div>
    <div class="card"><div class="label" data-i18n="gui_language">Language</div><div class="value" id="d-lang">—</div></div>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:14px;">
    <button class="btn btn-primary" onclick="testConn()" data-i18n="gui_test_conn">🔗 Test Connection</button>
    <button class="btn btn-primary" onclick="loadDashboard()" data-i18n="gui_refresh">🔄 Refresh</button>
  </div>
  <div class="log-box" id="d-log">[Ready]</div>
</div>

<!-- ═══ Rules ═══ -->
<div class="panel" id="p-rules">
  <div class="toolbar">
    <span style="font-size:1.1rem;font-weight:700;color:var(--accent2)" data-i18n="gui_tab_rules">Rules</span>
    <span class="badge" id="r-badge">0</span>
    <button class="btn btn-sm" style="margin-left:8px;background:var(--dim);color:#fff" onclick="openModal('m-help')" data-i18n="gui_param_guide">📖 Parameter Guide</button>
    <div class="spacer"></div>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-event')" data-i18n="gui_add_event">📋 + Event</button>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-traffic')" data-i18n="gui_add_traffic">🚦 + Traffic</button>
    <button class="btn btn-warn btn-sm" onclick="openModal('m-bw')" data-i18n="gui_add_bw">📊 + BW/Vol</button>
    <button class="btn btn-danger btn-sm" onclick="deleteSelected()" data-i18n="gui_delete">🗑 Delete</button>
  </div>
  <table class="rule-table">
    <thead><tr><th style="width:30px"><input type="checkbox" id="r-chkall" onchange="toggleAll(this)"></th><th data-i18n="gui_col_type">Type</th><th data-i18n="gui_col_name">Name</th><th data-i18n="gui_col_condition">Condition</th><th data-i18n="gui_col_filters">Filters</th><th style="width:50px" data-i18n="gui_col_edit">Edit</th></tr></thead>
    <tbody id="r-body"></tbody>
  </table>
</div>

<!-- ═══ Settings ═══ -->
<div class="panel" id="p-settings">
  <div id="s-form"></div>
  <div style="text-align:right;margin-top:16px;">
    <button class="btn btn-success" onclick="saveSettings()" data-i18n="gui_save_all">💾 Save All Settings</button>
  </div>
</div>

<!-- ═══ Actions ═══ -->
<div class="panel" id="p-actions">
  <div class="action-grid">
    <div class="action-card"><h3 data-i18n="gui_run_once">▶ Run Monitor Once</h3><p data-i18n="gui_run_once_desc">Execute full cycle: Health → Fetch → Analyze → Alert</p><button class="btn btn-primary" onclick="runAction('run')" data-i18n="gui_run_btn">Run</button></div>
    <div class="action-card"><h3 data-i18n="gui_debug_mode">🔍 Debug Mode</h3><p data-i18n="gui_debug_desc">Sandbox mode — no alerts, no state updates</p>
      <div class="form-row" style="margin-bottom:8px;">
        <div class="form-group"><label data-i18n="gui_window_min">Window (min)</label><input id="a-debug-mins" value="30"></div>
        <div class="form-group"><label data-i18n="gui_policy_dec">Policy Dec.</label><select id="a-debug-pd"><option value="1" data-i18n="gui_pd_blocked">Blocked</option><option value="2" data-i18n="gui_pd_allowed">Allowed</option><option value="3" data-i18n="gui_pd_all" selected>All</option></select></div>
      </div>
      <button class="btn btn-primary" onclick="runDebug()" data-i18n="gui_run_debug">Run Debug</button>
    </div>
    <div class="action-card"><h3 data-i18n="gui_test_alert">📧 Send Test Alert</h3><p data-i18n="gui_test_alert_desc">Verify Email / LINE / Webhook delivery</p><button class="btn btn-primary" onclick="runAction('test-alert')" data-i18n="gui_send">Send</button></div>
    <div class="action-card"><h3 data-i18n="gui_best_practices">📋 Load Best Practices</h3><p data-i18n="gui_best_practices_desc">Replace ALL existing rules with recommended defaults</p><button class="btn btn-danger" onclick="confirmBestPractices()" data-i18n="gui_load">Load</button></div>
  </div>
  <h3 style="color:var(--accent2);margin-bottom:8px;" data-i18n="gui_output">Output</h3>
  <div class="log-box" id="a-log"></div>
</div>

<!-- ═══ Modals ═══ -->
<!-- Event -->
<div class="modal-bg" id="m-event"><div class="modal">
  <h2><span data-i18n="gui_add_event_rule" id="me-title">Add Event Rule</span></h2>
  <div class="form-group"><label data-i18n="gui_category">Category</label><select id="ev-cat" onchange="populateEvents()"><option value="" data-i18n="gui_select">Select...</option></select></div>
  <div class="form-group"><label data-i18n="gui_event_type">Event Type</label><select id="ev-type"><option value="" data-i18n="gui_select_first">Select category first</option></select></div>
  <fieldset><legend data-i18n="gui_threshold">Threshold</legend>
    <div class="form-group"><label data-i18n="gui_type">Type</label><div class="radio-group"><label><input type="radio" name="ev-tt" value="immediate" checked> <span data-i18n="gui_tt_immediate">Immediate</span></label><label><input type="radio" name="ev-tt" value="count"> <span data-i18n="gui_tt_count">Cumulative</span></label></div></div>
    <div class="form-row-3">
      <div class="form-group"><label data-i18n="gui_count">Count</label><input id="ev-cnt" type="number" value="5"></div>
      <div class="form-group"><label data-i18n="gui_window_min">Window (min)</label><input id="ev-win" type="number" value="10"></div>
      <div class="form-group"><label data-i18n="gui_cooldown">Cooldown (min)</label><input id="ev-cd" type="number" value="10"></div>
    </div>
  </fieldset>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-event')" data-i18n="gui_cancel">Cancel</button><button class="btn btn-success" onclick="saveEvent()" data-i18n="gui_save">💾 Save</button></div>
</div></div>

<!-- Traffic -->
<div class="modal-bg" id="m-traffic"><div class="modal">
  <h2><span data-i18n="gui_add_traffic_rule" id="mt-title">Add Traffic Rule</span></h2>
  <div class="form-group"><label data-i18n="gui_rule_name">Rule Name</label><input id="tr-name"></div>
  <fieldset><legend data-i18n="gui_policy_dec">Policy Decision</legend><div class="radio-group">
    <label><input type="radio" name="tr-pd" value="2" checked> <span data-i18n="gui_pd_blocked">Blocked</span></label>
    <label><input type="radio" name="tr-pd" value="1"> <span data-i18n="gui_pd_potential">Potential</span></label>
    <label><input type="radio" name="tr-pd" value="0"> <span data-i18n="gui_pd_allowed">Allowed</span></label>
    <label><input type="radio" name="tr-pd" value="-1"> <span data-i18n="gui_pd_all">All</span></label>
  </div></fieldset>
  <fieldset><legend data-i18n="gui_col_filters">Filters</legend>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_port">Port</label><input id="tr-port" placeholder="e.g. 80, 443"></div><div class="form-group"><label data-i18n="gui_protocol">Protocol</label><select id="tr-proto"><option value="" data-i18n="gui_both">Both</option><option value="6" data-i18n="gui_tcp">TCP</option><option value="17" data-i18n="gui_udp">UDP</option></select></div></div>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_source">Source (Label/IP)</label><input id="tr-src" placeholder="e.g. role=Web, 10.0.0.0/8, 192.168.1.1"></div><div class="form-group"><label data-i18n="gui_dest">Destination (Label/IP)</label><input id="tr-dst" placeholder="e.g. app=DB, 10.1.1.5"></div></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_excludes">Excludes (Optional)</legend>
    <div class="form-row-3"><div class="form-group"><label data-i18n="gui_ex_port">Exclude Port</label><input id="tr-expt" placeholder="e.g. 22"></div><div class="form-group"><label data-i18n="gui_ex_src">Exclude Source</label><input id="tr-exsrc" placeholder="e.g. env=Kube, 10.9.9.9"></div><div class="form-group"><label data-i18n="gui_ex_dest">Exclude Destination</label><input id="tr-exdst" placeholder="e.g. 8.8.8.8"></div></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_threshold">Threshold</legend>
    <div class="form-row-3"><div class="form-group"><label data-i18n="gui_count">Count</label><input id="tr-cnt" type="number" value="10"></div><div class="form-group"><label data-i18n="gui_window_min">Window (min)</label><input id="tr-win" type="number" value="10"></div><div class="form-group"><label data-i18n="gui_cooldown">Cooldown (min)</label><input id="tr-cd" type="number" value="10"></div></div>
  </fieldset>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-traffic')" data-i18n="gui_cancel">Cancel</button><button class="btn btn-success" onclick="saveTraffic()" data-i18n="gui_save">💾 Save</button></div>
</div></div>

<!-- BW/Volume -->
<div class="modal-bg" id="m-bw"><div class="modal">
  <h2><span data-i18n="gui_add_bw_rule" id="mb-title">Add Bandwidth / Volume Rule</span></h2>
  <div class="form-group"><label data-i18n="gui_rule_name">Rule Name</label><input id="bw-name"></div>
  <fieldset><legend data-i18n="gui_metric_type">Metric Type</legend><div class="radio-group">
    <label><input type="radio" name="bw-mt" value="bandwidth" checked> <span data-i18n="gui_mt_bw">Bandwidth (Mbps, Max)</span></label>
    <label><input type="radio" name="bw-mt" value="volume"> <span data-i18n="gui_mt_vol">Volume (MB, Sum)</span></label>
  </div></fieldset>
  <fieldset><legend data-i18n="gui_policy_dec">Policy Decision</legend><div class="radio-group">
    <label><input type="radio" name="bw-pd" value="2"> <span data-i18n="gui_pd_blocked">Blocked</span></label>
    <label><input type="radio" name="bw-pd" value="1"> <span data-i18n="gui_pd_potential">Potential</span></label>
    <label><input type="radio" name="bw-pd" value="0"> <span data-i18n="gui_pd_allowed">Allowed</span></label>
    <label><input type="radio" name="bw-pd" value="-1" checked> <span data-i18n="gui_pd_all">All</span></label>
  </div></fieldset>
  <fieldset><legend data-i18n="gui_col_filters">Filters</legend>
    <div class="form-row-3"><div class="form-group"><label data-i18n="gui_port">Port</label><input id="bw-port" placeholder="e.g. 443"></div><div class="form-group"><label data-i18n="gui_source">Source (Label/IP)</label><input id="bw-src" placeholder="e.g. role=Web, 10.0.0.0/8"></div><div class="form-group"><label data-i18n="gui_dest">Destination (Label/IP)</label><input id="bw-dst" placeholder="e.g. app=DB, 10.1.1.5"></div></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_excludes">Excludes (Optional)</legend>
    <div class="form-row-3"><div class="form-group"><label data-i18n="gui_ex_port">Exclude Port</label><input id="bw-expt" placeholder="e.g. 22"></div><div class="form-group"><label data-i18n="gui_ex_src">Exclude Source</label><input id="bw-exsrc" placeholder="e.g. env=Kube, 10.9.9.9"></div><div class="form-group"><label data-i18n="gui_ex_dest">Exclude Destination</label><input id="bw-exdst" placeholder="e.g. 8.8.8.8"></div></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_threshold">Threshold</legend>
    <div class="form-row-3"><div class="form-group"><label data-i18n="gui_value">Value</label><input id="bw-val" type="number" value="100"></div><div class="form-group"><label data-i18n="gui_window_min">Window (min)</label><input id="bw-win" type="number" value="10"></div><div class="form-group"><label data-i18n="gui_cooldown">Cooldown (min)</label><input id="bw-cd" type="number" value="30"></div></div>
  </fieldset>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-bw')" data-i18n="gui_cancel">Cancel</button><button class="btn btn-success" onclick="saveBW()" data-i18n="gui_save">💾 Save</button></div>
</div></div>

<!-- Help / Parameter Guide -->
<div class="modal-bg" id="m-help"><div class="modal" style="max-width:600px;">
  <h2>📖 Parameter Guide (API 25.2)</h2>
  <div style="color:var(--dim);line-height:1.6;font-size:0.95rem;">
    <p>Illumio PCE Monitor leverages the standard Illumio Traffic Analysis REST API parameters.</p>
    <h3 style="color:#fff;margin-top:12px">Filters & Excludes</h3>
    <ul style="padding-left:20px;margin-bottom:12px">
      <li><strong>Label format:</strong> <code>key=value</code> (e.g., <code>role=Web</code>, <code>env=Production</code>, <code>app=Database</code>). Must exactly match the PCE label keys and values.</li>
      <li><strong>IP List/CIDR format:</strong> Standard CIDR notation (e.g., <code>10.0.0.0/8</code>) or exact IPs (e.g., <code>192.168.1.50</code>).</li>
      <li><strong>Port format:</strong> Integer port numbers (e.g., <code>80</code>, <code>443</code>, <code>3306</code>).</li>
    </ul>

    <h3 style="color:#fff;margin-top:12px">Policy Decisions</h3>
    <ul style="padding-left:20px;margin-bottom:12px">
      <li><strong>Blocked:</strong> Traffic explicitly dropped by policy.</li>
      <li><strong>Potential:</strong> Traffic that <em>would</em> be blocked if the workload were placed into Enforced mode.</li>
      <li><strong>Allowed:</strong> Traffic permitted by policy.</li>
    </ul>
  </div>
  <div class="modal-actions"><button class="btn btn-primary" onclick="closeModal('m-help')">Close window</button></div>
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
let _translations={};

async function loadTranslations(){
  _translations=await api('/api/ui_translations');
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const k=el.getAttribute('data-i18n');
    if(_translations[k]){
      if(el.tagName==='INPUT'&&el.type==='button') el.value=_translations[k];
      else el.textContent=_translations[k];
    }
  });
}

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
  if(d.theme) document.documentElement.setAttribute('data-theme', d.theme);
  await loadTranslations();
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
function openModal(id,isEdit){
  _editIdx=isEdit??null;$(id).classList.add('show');if(id==='m-event'&&!Object.keys(_catalog).length)loadCatalog();
  // Update modal title
  let target;
  if(id==='m-event') target=$('me-title');
  else if(id==='m-traffic') target=$('mt-title');
  else if(id==='m-bw') target=$('mb-title');
  if(target){
    const baseKey = id==='m-event'?'gui_add_event_rule':id==='m-traffic'?'gui_add_traffic_rule':'gui_add_bw_rule';
    const editKey = id==='m-event'?'gui_edit_event_rule':id==='m-traffic'?'gui_edit_traffic_rule':'gui_edit_bw_rule';
    const key = _editIdx!==null ? editKey : baseKey;
    target.setAttribute('data-i18n', key);
    if(_translations[key]) target.textContent=_translations[key];
  }
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
  try {
    const r=await api('/api/rules/'+idx);
    if(!r || r.error){toast('Rule not found','err');return}
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
      $('bw-expt').value=r.ex_port||'';
      $('bw-exsrc').value=r.ex_src_label||r.ex_src_ip||'';
      $('bw-exdst').value=r.ex_dst_label||r.ex_dst_ip||'';
      $('bw-val').value=r.threshold_count||100;
      $('bw-win').value=r.threshold_window||10;
      $('bw-cd').value=r.cooldown_minutes||30;
      openModal('m-bw',idx);
    }
  } catch(e) {
    console.error(e);
    alert('UI Error: ' + e.message);
  }
}

async function saveEvent(){
  const cat=$('ev-cat').value,ev=$('ev-type').value;
  if(!cat||!ev){toast('Select category and event','err');return}
  const name=(_catalog[cat]||{})[ev]||ev;
  const data={name,filter_value:ev,threshold_type:rv('ev-tt'),threshold_count:$('ev-cnt').value,threshold_window:$('ev-win').value,cooldown_minutes:$('ev-cd').value};
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
  const data={
    name,rule_type:rv('bw-mt'),pd:rv('bw-pd'),
    port:$('bw-port').value,src:$('bw-src').value,dst:$('bw-dst').value,
    ex_port:$('bw-expt').value,ex_src:$('bw-exsrc').value,ex_dst:$('bw-exdst').value,
    threshold_count:$('bw-val').value,threshold_window:$('bw-win').value,cooldown_minutes:$('bw-cd').value
  };
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
  <fieldset><legend data-i18n="gui_api_conn">API Connection</legend>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_url">URL</label><input id="s-url" value="${a.url||''}"></div><div class="form-group"><label data-i18n="gui_org_id">Org ID</label><input id="s-org" value="${a.org_id||''}"></div></div>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_api_key">API Key</label><input id="s-key" value="${a.key||''}"></div><div class="form-group"><label data-i18n="gui_api_secret">API Secret</label><input id="s-sec" type="password" value="${a.secret||''}"></div></div>
    <div class="chk"><label><input type="checkbox" id="s-ssl" ${a.verify_ssl?'checked':''}> <span data-i18n="gui_verify_ssl">Verify SSL</span></label></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_email_smtp">Email & SMTP</legend>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_sender">Sender</label><input id="s-sender" value="${e.sender||''}"></div><div class="form-group"><label data-i18n="gui_recipients">Recipients (comma)</label><input id="s-rcpt" value="${(e.recipients||[]).join(', ')}"></div></div>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_smtp_host">SMTP Host</label><input id="s-smhost" value="${sm.host||''}"></div><div class="form-group"><label data-i18n="gui_port">Port</label><input id="s-smport" value="${sm.port||25}"></div></div>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_user">User</label><input id="s-smuser" value="${sm.user||''}"></div><div class="form-group"><label data-i18n="gui_password">Password</label><input id="s-smpass" type="password" value="${sm.password||''}"></div></div>
    <div style="display:flex;gap:20px"><div class="chk"><label><input type="checkbox" id="s-tls" ${sm.enable_tls?'checked':''}> STARTTLS</label></div><div class="chk"><label><input type="checkbox" id="s-auth" ${sm.enable_auth?'checked':''}> Auth</label></div></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_alert_channels">Alert Channels</legend>
    <div style="display:flex;gap:20px;margin-bottom:12px"><div class="chk"><label><input type="checkbox" id="s-amail" ${active.includes('mail')?'checked':''}> 📧 <span data-i18n="gui_mail">Mail</span></label></div><div class="chk"><label><input type="checkbox" id="s-aline" ${active.includes('line')?'checked':''}> 📱 <span data-i18n="gui_line">LINE</span></label></div><div class="chk"><label><input type="checkbox" id="s-awh" ${active.includes('webhook')?'checked':''}> 🔗 <span data-i18n="gui_webhook">Webhook</span></label></div></div>
    <div class="form-row"><div class="form-group"><label data-i18n="gui_line_token">LINE Token</label><input id="s-ltok" value="${al.line_channel_access_token||''}"></div><div class="form-group"><label data-i18n="gui_line_target_id">LINE Target ID</label><input id="s-ltgt" value="${al.line_target_id||''}"></div></div>
    <div class="form-group"><label data-i18n="gui_webhook_url">Webhook URL</label><input id="s-whurl" value="${al.webhook_url||''}"></div>
  </fieldset>
  <fieldset><legend data-i18n="gui_lang_settings">Display & General</legend>
    <div class="chk" style="margin-bottom:12px"><label><input type="checkbox" id="s-hc" ${st.enable_health_check!==false?'checked':''}> <span data-i18n="gui_enable_hc">Enable PCE Health Check</span></label></div>
    <div class="form-row">
      <div class="form-group">
        <label data-i18n="gui_language">Language</label>
        <div class="radio-group">
          <label><input type="radio" name="s-lang" value="en" ${st.language!=='zh_TW'?'checked':''}> <span data-i18n="gui_lang_en">English</span></label>
          <label><input type="radio" name="s-lang" value="zh_TW" ${st.language==='zh_TW'?'checked':''}> <span data-i18n="gui_lang_zh">繁體中文</span></label>
        </div>
      </div>
      <div class="form-group">
        <label>Theme</label>
        <div class="radio-group">
          <label><input type="radio" name="s-theme" value="dark" ${st.theme!=='light'?'checked':''}> <span data-i18n="gui_theme_dark">Dark Theme</span></label>
          <label><input type="radio" name="s-theme" value="light" ${st.theme==='light'?'checked':''}> <span data-i18n="gui_theme_light">Light Theme</span></label>
        </div>
      </div>
    </div>
  </fieldset>`;
  await loadTranslations();
}
async function saveSettings(){
  const active=[];if($('s-amail').checked)active.push('mail');if($('s-aline').checked)active.push('line');if($('s-awh').checked)active.push('webhook');
  const theme = rv('s-theme');
  document.documentElement.setAttribute('data-theme', theme);
  await post('/api/settings',{
    api:{url:$('s-url').value,org_id:$('s-org').value,key:$('s-key').value,secret:$('s-sec').value,verify_ssl:$('s-ssl').checked},
    email:{sender:$('s-sender').value,recipients:$('s-rcpt').value.split(',').map(s=>s.trim()).filter(Boolean)},
    smtp:{host:$('s-smhost').value,port:parseInt($('s-smport').value)||25,user:$('s-smuser').value,password:$('s-smpass').value,enable_tls:$('s-tls').checked,enable_auth:$('s-auth').checked},
    alerts:{active,line_channel_access_token:$('s-ltok').value,line_target_id:$('s-ltgt').value,webhook_url:$('s-whurl').value},
    settings:{language:rv('s-lang'), theme: theme, enable_health_check:$('s-hc').checked}
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
