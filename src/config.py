import json
import os
import time
import logging
from src.utils import Colors
from src.i18n import t, set_language

logger = logging.getLogger(__name__)

# Determine Root Directory (parent of the package)
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PKG_DIR)
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")

# Default configuration template
_DEFAULT_CONFIG = {
    "api": {"url": "https://pce.example.com:8443", "org_id": "1", "key": "", "secret": "", "verify_ssl": True},
    "alerts": {
        "active": ["mail"],
        "line_channel_access_token": "",
        "line_target_id": "",
        "webhook_url": ""
    },
    "email": {"sender": "monitor@localhost", "recipients": ["admin@example.com"]},
    "smtp": {"host": "localhost", "port": 25, "user": "", "password": "", "enable_auth": False, "enable_tls": False},
    "settings": {"enable_health_check": True, "language": "en", "theme": "light"},
    "rules": []
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merges override into base. Lists and non-dict values are replaced."""
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


class ConfigManager:
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = json.loads(json.dumps(_DEFAULT_CONFIG))  # deep copy
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = _deep_merge(self.config, data)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.error(f"Error loading config: {e}")
                print(f"{Colors.FAIL}{t('error_loading_config', error=e)}{Colors.ENDC}")
            finally:
                lang = self.config.get("settings", {}).get("language", "en")
                set_language(lang)

    def save(self):
        try:
            # Atomic write: write to temp file first, then rename
            tmp_file = self.config_file + ".tmp"
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            # On Windows, os.replace handles atomic rename
            os.replace(tmp_file, self.config_file)
            lang = self.config.get("settings", {}).get("language", "en")
            set_language(lang)
            print(f"{Colors.GREEN}{t('config_saved')}{Colors.ENDC}")
            logger.info("Configuration saved.")
        except (IOError, OSError) as e:
            logger.error(f"Error saving config: {e}")
            print(f"{Colors.FAIL}{t('error_saving_config', error=e)}{Colors.ENDC}")

    def add_or_update_rule(self, new_rule):
        for i, rule in enumerate(self.config["rules"]):
            is_same = False
            if new_rule["type"] == rule["type"]:
                if new_rule["type"] == "event" and new_rule.get("filter_value") == rule.get("filter_value"):
                    is_same = True
                elif new_rule["type"] in ["traffic", "bandwidth", "volume"] and new_rule["name"] == rule["name"]:
                    is_same = True

            if is_same:
                new_rule["id"] = rule["id"]
                self.config["rules"][i] = new_rule
                print(f"{Colors.WARNING}{t('rule_overwritten')}{Colors.ENDC}")
                self.save()
                return
        self.config["rules"].append(new_rule)
        self.save()

    def remove_rules_by_index(self, index_list):
        sorted_indices = sorted(index_list, reverse=True)
        count: int = 0
        for idx in sorted_indices:
            if 0 <= idx < len(self.config["rules"]):
                removed = self.config["rules"].pop(idx)
                print(t('rule_deleted', name=removed['name']))
                count = count + 1
        if count > 0:
            self.save()

    def load_best_practices(self):
        print(f"{Colors.BLUE}{t('loading_best_practices')}{Colors.ENDC}")
        self.config["rules"] = []
        ts = int(time.time())
        bps = [
            ("Agent Tampering Detected", "agent.tampering", "immediate", 1, 10, 30),
            ("Agent Offline", "system_task.agent_offline_check", "immediate", 1, 10, 30),
            ("API Authentication Failed", "request.authentication_failed", "count", 5, 10, 30),
            ("Login Failed", "user.login_failed", "count", 5, 10, 30)
        ]
        for i, (name, etype, ttype, cnt, win, cd) in enumerate(bps):
            self.config["rules"].append({
                "id": ts + i, "type": "event", "name": name,
                "filter_key": "event_type", "filter_value": etype,
                "desc": "Best Practice", "rec": "Check Logs",
                "threshold_type": ttype, "threshold_count": cnt,
                "threshold_window": win, "cooldown_minutes": cd
            })
        self.config["rules"].append({
            "id": ts + 100, "type": "traffic", "name": "High Blocked Traffic", "pd": 2,
            "port": None, "proto": None, "src_label": None, "dst_label": None,
            "desc": "Blocked traffic exceeds threshold",
            "rec": "Check Policy", "threshold_type": "count", "threshold_count": 10,
            "threshold_window": 10, "cooldown_minutes": 30
        })
        self.save()
