import json
import os
import time
from .utils import Colors

# Determine Root Directory (parent of the package)
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PKG_DIR)
CONFIG_FILE = os.path.join(ROOT_DIR, "illumio_pce_config.json")

class ConfigManager:
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = {
            "api": {"url": "https://pce.example.com:8443", "org_id": "1", "key": "", "secret": "", "verify_ssl": True},
            "email": {"sender": "monitor@localhost", "recipients": ["admin@example.com"]},
            "smtp": {"host": "localhost", "port": 25, "user": "", "password": "", "enable_auth": False, "enable_tls": False},
            "settings": {"enable_health_check": True},
            "rules": []
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.config.update(data)
                    if "settings" not in self.config: self.config["settings"] = {"enable_health_check": True}
                    if "smtp" not in self.config: 
                        self.config["smtp"] = {"host": "localhost", "port": 25, "user": "", "password": "", "enable_auth": False, "enable_tls": False}
            except Exception as e:
                print(f"{Colors.FAIL}Error loading config: {e}{Colors.ENDC}")

    def save(self):
        try:
            with open(self.config_file, 'w') as f: json.dump(self.config, f, indent=4)
            print(f"{Colors.GREEN}設定已儲存。{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Error saving config: {e}{Colors.ENDC}")

    def add_or_update_rule(self, new_rule):
        for i, rule in enumerate(self.config["rules"]):
            is_same = False
            if new_rule["type"] == rule["type"]:
                if new_rule["type"] == "event" and new_rule.get("filter_value") == rule.get("filter_value"): is_same = True
                elif new_rule["type"] in ["traffic", "bandwidth", "volume"] and new_rule["name"] == rule["name"]: is_same = True
            
            if is_same:
                new_rule["id"] = rule["id"]
                self.config["rules"][i] = new_rule
                print(f"{Colors.WARNING}規則已存在，已覆蓋更新設定。{Colors.ENDC}")
                self.save()
                return
        self.config["rules"].append(new_rule)
        self.save()

    def remove_rules_by_index(self, index_list):
        sorted_indices = sorted(index_list, reverse=True)
        count = 0
        for idx in sorted_indices:
            if 0 <= idx < len(self.config["rules"]):
                removed = self.config["rules"].pop(idx)
                print(f"已刪除: {removed['name']}")
                count += 1
        if count > 0: self.save()

    def load_best_practices(self):
        print(f"{Colors.BLUE}正在載入最佳實踐 (會清空現有規則)...{Colors.ENDC}")
        self.config["rules"] = []
        ts = int(time.time())
        bps = [
            ("Agent 遭到竄改", "agent.tampering", "immediate", 1, 10, 30),
            ("Agent 離線", "system_task.agent_offline_check", "immediate", 1, 10, 30),
            ("API 認證失敗", "request.authentication_failed", "count", 5, 10, 30),
            ("登入失敗", "user.login_failed", "count", 5, 10, 30)
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
            "id": ts + 100, "type": "traffic", "name": "大量被阻擋流量", "pd": 2,
            "port": None, "proto": None, "src_label": None, "dst_label": None, "desc": "Blocked Traffic",
            "rec": "Check Policy", "threshold_type": "count", "threshold_count": 10, 
            "threshold_window": 10, "cooldown_minutes": 30
        })
        self.save()
