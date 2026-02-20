import os
import datetime
import sys
import io
from flask import Flask, render_template, request, jsonify, redirect, url_for
from src.config import ConfigManager
from src.api_client import ApiClient
from src.reporter import Reporter
from src.analyzer import Analyzer
from src.i18n import t

# Identify the absolute path to template directory
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)

# Global ConfigManager instance to be injected
cm = None

def init_app(config_manager: ConfigManager):
    global cm
    cm = config_manager

@app.route("/")
def index():
    if not cm:
        return "ConfigManager not initialized", 500
    
    # Pass necessary config data to the template
    return render_template(
        "index.html", 
        version="1.0.0",
        config=cm.config,
        lang=cm.config.get("settings", {}).get("language", "en")
    )

@app.route("/api/config", methods=["GET"])
def get_config():
    if not cm:
        return jsonify({"error": "Not initialized"}), 500
    cfg = dict(cm.config)
    if "mail" not in cfg:
        cfg["mail"] = {}
    return jsonify(cfg)

@app.route("/api/rules", methods=["GET"])
def get_rules():
    if not cm:
        return jsonify({"error": "Not initialized"}), 500
    return jsonify(cm.config.get("rules", []))

@app.route("/api/rules", methods=["POST"])
def save_rule():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        data = request.json
        if not data: return jsonify({"error": "No data provided"}), 400
        
        # If modifying a rule, we might get an ID or index. We handle replacing by finding the exact same rule,
        # but the ConfigManager's `add_or_update_rule` naturally handles replacing if the `id` matches or we can just 
        # delete by index and append if an explicit index is provided.
        # Actually ConfigManager `add_or_update_rule` looks for exact matches of name/desc sometimes, but wait - 
        # settings.py just appended a new one with a new ID after deleting.
        if 'index' in data:
            idx = int(data['index'])
            if 0 <= idx < len(cm.config.get("rules", [])):
                cm.remove_rules_by_index([idx])
            del data['index']
            
        if 'id' not in data:
            data['id'] = int(datetime.datetime.now().timestamp())
            
        cm.add_or_update_rule(data)
        return jsonify({"success": True, "rule": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rules/<int:idx>", methods=["DELETE"])
def delete_rule(idx):
    if not cm:
        return jsonify({"error": "Not initialized"}), 500
    try:
        if 0 <= idx < len(cm.config.get("rules", [])):
            cm.remove_rules_by_index([idx])
            return jsonify({"success": True})
        return jsonify({"error": "Rule not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/settings", methods=["GET"])
def get_settings():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    return jsonify({
        "api": cm.config.get("api", {}),
        "mail": cm.config.get("mail", {}),
        "alerts": cm.config.get("alerts", {}),
        "settings": cm.config.get("settings", {})
    })

@app.route("/api/settings", methods=["POST"])
def update_settings():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        data = request.json
        if 'api' in data: cm.config['api'] = data['api']
        if 'mail' in data: cm.config['mail'] = data['mail']
        if 'alerts' in data: cm.config['alerts'] = data['alerts']
        if 'settings' in data: cm.config['settings'] = data['settings']
        cm.save()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/run", methods=["POST"])
def run_monitor():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        api = ApiClient(cm)
        rep = Reporter(cm)
        ana = Analyzer(cm, api, rep)
        ana.run_analysis()
        rep.send_alerts()
        return jsonify({"success": True, "message": "Manual run completed successfully!"})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/actions/test_alert", methods=["POST"])
def test_alert():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        Reporter(cm).send_alerts(force_test=True)
        return jsonify({"success": True, "message": "Test Alert Dispatched!"})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/actions/best_practices", methods=["POST"])
def load_best_practices():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        cm.load_best_practices()
        return jsonify({"success": True, "message": "Best practices loaded successfully!"})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/actions/debug", methods=["POST"])
def debug_mode():
    if not cm: return jsonify({"error": "Not initialized"}), 500
    try:
        api = ApiClient(cm)
        rep = Reporter(cm)
        ana = Analyzer(cm, api, rep)
        
        # Capture stdout for debug output to send to frontend
        captured_out = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_out
        try:
            ana.run_debug_mode(mins=60, pd_sel=3)
        finally:
            sys.stdout = original_stdout
            
        return jsonify({"success": True, "log": captured_out.getvalue()})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/actions/shutdown", methods=["POST"])
def shutdown_server():
    import threading
    import signal
    def kill_server():
        try:
            # Send SIGINT to trigger KeyboardInterrupt on main thread
            os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            os._exit(1)
            
    threading.Timer(0.5, kill_server).start()
    return jsonify({"success": True, "message": "Server is shutting down..."})

def start_server(host="0.0.0.0", port=8080):
    print(f"\n{t('starting_web_gui')} http://{host}:{port}")
    # Disable werkzeug logging directly to keep terminal clean
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # For standalone testing
    test_cm = ConfigManager()
    init_app(test_cm)
    start_server("127.0.0.1", 8080)
