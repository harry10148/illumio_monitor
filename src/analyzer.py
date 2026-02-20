import datetime
import json
import gc
from collections import Counter
import os
from src.utils import Colors, format_unit, safe_input
from src.i18n import t

# Refine Root Dir for State File
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PKG_DIR)
STATE_FILE = os.path.join(ROOT_DIR, "illumio_pce_state.json")

class Analyzer:
    def __init__(self, config_manager, api_client, reporter):
        self.cm = config_manager
        self.api = api_client
        self.reporter = reporter
        self.state = {
            "last_check": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "history": {},
            "alert_history": {},
            "processed_ids": []
        }
        self.load_state()

    def load_state(self):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                self.state.update(data)
        except: pass

    def save_state(self):
        self.state["last_check"] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        # Prune history
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=2)
        new_history = {}
        for rid, records in self.state.get("history", {}).items():
            valid = []
            for rec in records:
                try:
                    ts = datetime.datetime.strptime(rec['t'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                    if ts > cutoff: valid.append(rec)
                except: pass
            if valid: new_history[rid] = valid
        self.state["history"] = new_history
        
        if len(self.state["processed_ids"]) > 2000:
            self.state["processed_ids"] = self.state["processed_ids"][-2000:]
            
        with open(STATE_FILE, 'w') as f: json.dump(self.state, f)

    def calculate_mbps(self, flow):
        # Hybrid Calculation: Interval vs Total
        delta_bytes = float(flow.get("dst_dbo") or flow.get("dbo") or 0) + float(flow.get("dst_dbi") or flow.get("dbi") or 0)
        ddms = float(flow.get("ddms") or 0)
        
        if delta_bytes > 0 and ddms > 0:
            val = (delta_bytes * 8.0) / (ddms / 1000.0) / 1000000.0
            return val, "(Interval)", delta_bytes, ddms
            
        # Fallback to Total if Interval is 0
        tbo = float(flow.get("dst_tbo") or flow.get("tbo") or flow.get("dst_bo") or 0)
        tbi = float(flow.get("dst_tbi") or flow.get("tbi") or flow.get("dst_bi") or 0)
        total_bytes = tbo + tbi
        tdms = float(flow.get("tdms") or 0)
        
        # If tdms is missing or small, use default interval (e.g. 10 mins) to avoid division by zero or huge numbers
        if tdms < 1000: tdms = float(flow.get("interval_sec", 600)) * 1000
        
        if total_bytes > 0 and tdms > 0:
            val = (total_bytes * 8.0) / (tdms / 1000.0) / 1000000.0
            return val, "(Avg)", total_bytes, tdms
            
        return 0.0, "", 0.0, 0.0

    def calculate_volume_mb(self, flow):
        delta_bytes = float(flow.get("dst_dbo") or flow.get("dbo") or 0) + float(flow.get("dst_dbi") or flow.get("dbi") or 0)
        if delta_bytes > 0: return delta_bytes / 1024 / 1024, "(Interval)"
        
        tbo = float(flow.get("dst_tbo") or flow.get("tbo") or flow.get("dst_bo") or 0)
        tbi = float(flow.get("dst_tbi") or flow.get("tbi") or flow.get("dst_bi") or 0)
        return (tbo + tbi) / 1024 / 1024, "(Total)"

    def check_flow_match(self, rule, f, start_time_limit):
        # Dynamic Sliding Window Check
        if start_time_limit:
            ts_str = f.get("timestamp")
            if ts_str:
                try: 
                    f_time = datetime.datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=datetime.timezone.utc)
                except:
                    try: f_time = datetime.datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                    except: f_time = None
                
                if f_time and f_time < start_time_limit: return False

        # Criteria Check
        if rule["type"] == "traffic":
            p = f.get("pd")
            # Logic to handle different flow formats
            raw_dec = str(f.get("policy_decision", "")).lower()
            flow_pd = -1
            if p is not None: flow_pd = int(p)
            elif "blocked" in raw_dec and "potentially" not in raw_dec: flow_pd = 2
            elif "potentially" in raw_dec: flow_pd = 1
            elif "allowed" in raw_dec: flow_pd = 0
            
            target_pd = rule.get("pd", 2)
            if target_pd != -1 and flow_pd != target_pd: return False

        if rule.get("port"):
            f_port = f.get("dst_port") or f.get("service", {}).get("port")
            try: 
                if not f_port or int(f_port) != int(rule["port"]): return False
            except: return False
        
        if rule.get("proto"):
            f_proto = f.get("proto") or f.get("service", {}).get("proto")
            try:
                if not f_proto or int(f_proto) != int(rule.get("proto")): return False
            except: return False

        # Labels & IPs
        if rule.get("src_label") and not self._check_flow_labels(f.get('src',{}), rule["src_label"]): return False
        if rule.get("dst_label") and not self._check_flow_labels(f.get('dst', {}), rule["dst_label"]): return False
        if rule.get("src_ip_in") and not self._check_ip_filter(f.get('src',{}), rule["src_ip_in"]): return False
        if rule.get("dst_ip_in") and not self._check_ip_filter(f.get('dst',{}), rule["dst_ip_in"]): return False
        
        # Excludes
        if rule.get("ex_port"):
            f_port = f.get("dst_port") or f.get("service", {}).get("port")
            try:
                if f_port and int(f_port) == int(rule["ex_port"]): return False
            except: pass
        if rule.get("ex_src_label") and self._check_flow_labels(f.get('src',{}), rule["ex_src_label"]): return False
        if rule.get("ex_dst_label") and self._check_flow_labels(f.get('dst',{}), rule["ex_dst_label"]): return False
        if rule.get("ex_src_ip") and self._check_ip_filter(f.get('src',{}), rule["ex_src_ip"]): return False
        if rule.get("ex_dst_ip") and self._check_ip_filter(f.get('dst',{}), rule["ex_dst_ip"]): return False

        return True

    def _check_flow_labels(self, flow_side, filter_str):
        if not filter_str: return True
        try:
            fk, fv = filter_str.split('=')
            for l in flow_side.get('workload', {}).get('labels', []):
                if l.get('key') == fk.strip() and l.get('value') == fv.strip(): return True
            return False
        except: return False

    def _check_ip_filter(self, flow_side, filter_val):
        if not filter_val: return True
        if flow_side.get('ip') == filter_val: return True
        for ipl in flow_side.get('ip_lists', []):
            if ipl.get('name') == filter_val: return True
        return False

    def get_traffic_details_key(self, flow):
        src = flow.get('src', {})
        dst = flow.get('dst', {})
        svc = flow.get('service', {})
        s_name = src.get('workload', {}).get('name') or src.get('ip', 'N/A')
        d_name = dst.get('workload', {}).get('name') or dst.get('ip', 'N/A')
        port = svc.get('port', 'All') or flow.get('dst_port', 'All')
        return f"{s_name} -> {d_name} [{port}]"

    def run_analysis(self):
        # 1. Health Check
        if self.cm.config["settings"].get("enable_health_check", True):
            print(f"{t('checking_pce_health')}...", end=" ", flush=True)
            status, msg = self.api.check_health()
            if status != 200:
                print(f"{Colors.FAIL}{t('status_error')}{Colors.ENDC}")
                self.reporter.add_health_alert({"time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "status": str(status), "details": msg[:200]})
            else:
                print(f"{Colors.GREEN}{t('status_ok')}{Colors.ENDC}")

        # 2. Events
        print(f"{t('checking_events')}...")
        events = self.api.fetch_events(self.state["last_check"]) 
        if events:
            print(t('found_events', count=len(events)))
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            for rule in [r for r in self.cm.config["rules"] if r["type"] == "event"]:
                matches = [e for e in events if rule["filter_value"] == e.get("event_type")]
                
                # Event History Logic for 'count' threshold
                if matches:
                    rid = str(rule["id"])
                    if rid not in self.state["history"]: self.state["history"][rid] = []
                    self.state["history"][rid].append({"t": now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), "c": len(matches)})
                
                # Check Threshold
                count_val = len(matches)
                if rule["threshold_type"] == "count":
                    win_minutes = rule.get("threshold_window", 10)
                    win_start = now_utc - datetime.timedelta(minutes=win_minutes)
                    # Sum history within window
                    count_val = sum(rec['c'] for rec in self.state.get("history", {}).get(str(rule["id"]), []) 
                                   if datetime.datetime.strptime(rec['t'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc) > win_start)

                if count_val >= rule["threshold_count"] and count_val > 0:
                    if self._check_cooldown(rule):
                        self.reporter.add_event_alert({
                            "time": matches[0].get("timestamp") if matches else "N/A",
                            "rule": rule["name"],
                            "desc": rule.get("desc"),
                            "severity": matches[0].get("severity", "info") if matches else "info",
                            "count": count_val,
                            "source": matches[0].get("created_by", {}).get("agent", {}).get("hostname", "System") if matches else "N/A",
                            "raw_data": matches[:5]
                        })

        # 3. Traffic
        tr_rules = [r for r in self.cm.config["rules"] if r["type"] in ["traffic", "bandwidth", "volume"]]
        if tr_rules:
            # Determine Max Window
            max_win = max([r.get('threshold_window', 10) for r in tr_rules])
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            start_dt = now_utc - datetime.timedelta(minutes=max_win + 2)
            
            # One-Pass: Stream results
            traffic_stream = self.api.execute_traffic_query_stream(
                start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'), 
                now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
                ["blocked", "potentially_blocked", "allowed"]
            )
            
            if traffic_stream:
                rule_results = {r['id']: {'max_val': 0.0, 'top_matches': []} for r in tr_rules}
                
                count_processed = 0
                for f in traffic_stream:
                    count_processed += 1
                    
                    # Pre-calculate metrics for this flow
                    bw_val, bw_note, _, _ = self.calculate_mbps(f)
                    vol_val, vol_note = self.calculate_volume_mb(f)
                    conn_val = int(f.get("num_connections") or f.get("count", 1))

                    for rule in tr_rules:
                        rid = rule['id']
                        # Dynamic Window check per rule
                        r_win = rule.get("threshold_window", 10)
                        r_start = now_utc - datetime.timedelta(minutes=r_win)
                        
                        if not self.check_flow_match(rule, f, r_start): continue

                        res = rule_results[rid]
                        
                        # Update Max/Sum based on type
                        if rule["type"] == "bandwidth":
                             if bw_val > res['max_val']: res['max_val'] = bw_val
                             if bw_val > float(rule.get("threshold_count", 0)):
                                 f_copy = f.copy()
                                 f_copy['_metric_val'] = bw_val
                                 f_copy['_metric_fmt'] = f"{format_unit(bw_val, 'bandwidth')} {bw_note}"
                                 res['top_matches'].append(f_copy)

                        elif rule["type"] == "volume":
                            res['max_val'] += vol_val
                            f_copy = f.copy()
                            f_copy['_metric_val'] = vol_val
                            f_copy['_metric_fmt'] = f"{format_unit(vol_val, 'volume')} {vol_note}"
                            res['top_matches'].append(f_copy)
                            
                        else: # Traffic Count
                            res['max_val'] += conn_val
                            f_copy = f.copy()
                            f_copy['_metric_val'] = conn_val
                            f_copy['_metric_fmt'] = str(conn_val)
                            res['top_matches'].append(f_copy)
                
                print(t('found_traffic', count=count_processed))
                
                # Check Triggers
                for rule in tr_rules:
                    rid = rule['id']
                    res = rule_results[rid]
                    val = res['max_val']
                    threshold = float(rule.get("threshold_count", 0))
                    
                    is_trigger = False
                    if rule["type"] == "bandwidth":
                         # Bandwidth triggers if ANY connection exceeded threshold (top_matches has data)
                         if len(res['top_matches']) > 0: is_trigger = True
                    else:
                         if val >= threshold: is_trigger = True
                    
                    if is_trigger and self._check_cooldown(rule):
                        # Sort and clip top matches
                        res['top_matches'].sort(key=lambda x: x.get('_metric_val', 0), reverse=True)
                        top_10 = res['top_matches'][:10]
                        
                        ctr = Counter([self.get_traffic_details_key(m) for m in top_10])
                        details = "<br>".join([f"{k}: {v}" for k,v in ctr.most_common(10)])
                        
                        alert_data = {
                            "rule": rule["name"],
                            "count": f"{val:.2f}" if rule['type'] != 'traffic' else str(int(val)),
                            "criteria": self._build_criteria_str(rule),
                            "details": details,
                            "raw_data": top_10
                        }
                        
                        if rule["type"] in ["bandwidth", "volume"]: self.reporter.add_metric_alert(alert_data)
                        else: self.reporter.add_traffic_alert(alert_data)

        self.save_state()
        gc.collect()

    def _check_cooldown(self, rule):
        rid = str(rule["id"])
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        last_alert = self.state.get("alert_history", {}).get(rid)
        
        cd_minutes = rule.get("cooldown_minutes", rule.get("threshold_window", 10))
        
        if last_alert:
            last_dt = datetime.datetime.strptime(last_alert, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
            if (now_utc - last_dt).total_seconds() < (cd_minutes * 60):
                print(f"{Colors.WARNING}{t('alert_cooldown', rule=rule['name'])}{Colors.ENDC}")
                return False
        
        print(f"{Colors.FAIL}{t('alert_trigger', rule=rule['name'])}{Colors.ENDC}")
        if "alert_history" not in self.state: self.state["alert_history"] = {}
        self.state["alert_history"][rid] = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        return True

    def _build_criteria_str(self, rule):
        crit = [f"Threshold: > {rule['threshold_count']}"]
        if rule.get('port'): crit.append(f"Port:{rule['port']}")
        return ", ".join(crit)


    def run_debug_mode(self, mins=None, pd_sel=None):
        print(f"\n{Colors.HEADER}{t('menu_debug_mode_title')}{Colors.ENDC}")
        
        # Determine max window from config
        max_win = 10 
        for r in self.cm.config['rules']:
            if r['type'] in ['traffic', 'bandwidth', 'volume']:
                w = r.get('threshold_window', 10)
                if w > max_win: max_win = w

        if mins is None:
            mins = safe_input(t('debug_query_mins'), int, allow_cancel=True)
        if not mins: mins = max_win + 2
        
        print(f"\nPolicy Decision {t('step_2_filters')}:")
        print("1. Blocked Only")
        print("2. Allowed Only")
        print("3. All (Blocked + Potential + Allowed) [預設]")
        
        if pd_sel is None:
            pd_sel = safe_input(t('please_select'), int, range(1,4), allow_cancel=True) or 3
            
        pds = ["blocked", "potentially_blocked", "allowed"]
        if pd_sel == 1: pds = ["blocked"]
        elif pd_sel == 2: pds = ["allowed"]
        
        now = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now - datetime.timedelta(minutes=mins)
        # Using the streaming method but collecting all results for debug analysis
        print(f"{t('debug_submit_query')} ({start_dt.strftime('%H:%M')} -> {now.strftime('%H:%M')})...")
        traffic_gen = self.api.execute_traffic_query_stream(start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'), now.strftime('%Y-%m-%dT%H:%M:%SZ'), pds)
        traffic = list(traffic_gen) if traffic_gen else []
        
        print(f"\n{Colors.CYAN}{t('debug_report_title')}{Colors.ENDC}")
        print(f"{t('debug_records_found')} {len(traffic)} (Window: {mins} mins)。")
        
        for rule in [r for r in self.cm.config["rules"] if r["type"] in ["traffic", "bandwidth", "volume"]]:
            print(f"\n{Colors.HEADER}{t('traffic_rule')}: {rule['name']} ({rule['type'].upper()}){Colors.ENDC}")
            rule_win = rule.get("threshold_window", 10)
            rule_start = now - datetime.timedelta(minutes=rule_win)
            
            matches = []
            for f in traffic:
                if self.check_flow_match(rule, f, rule_start):
                    f_copy = f.copy()
                    # Calculate metrics for matches
                    if rule["type"] == "bandwidth":
                        val, note, _, _ = self.calculate_mbps(f)
                        f_copy['_metric_val'] = val
                        f_copy['_metric_fmt'] = f"{format_unit(val, 'bandwidth')} {note}"
                    elif rule["type"] == "volume":
                        val_bytes, note = self.calculate_volume_mb(f)
                        f_copy['_metric_val'] = val_bytes 
                        f_copy['_metric_fmt'] = f"{format_unit(val_bytes, 'volume')} {note}"
                    else:
                        c = int(f.get("num_connections") or f.get("count", 1))
                        f_copy['_metric_val'] = c
                        f_copy['_metric_fmt'] = str(c)
                    matches.append(f_copy)

            print(f"  -> [Filter] Raw: {len(traffic)} -> Window({rule_win}m): {len(matches)} left")
            
            val = 0.0
            if rule["type"] == "bandwidth":
                # Find Max Bandwidth
                for m in matches: 
                    if m['_metric_val'] > val: val = m['_metric_val']
                print(f"  -> Max Bandwidth (Max): {val:.4f} Mbps")
            elif rule["type"] == "volume":
                # Sum Volume
                val = sum(m['_metric_val'] for m in matches)
                print(f"  -> Total Volume (Sum): {val:.4f} MB")
            else: # Traffic Count
                # Sum Count
                val = sum(m['_metric_val'] for m in matches)
                print(f"  -> Total Count (Sum): {int(val)}")
            
            is_trigger = False
            threshold = float(rule.get("threshold_count", 0))
            if rule["type"] == "bandwidth":
                 if matches and val > threshold: is_trigger = True
            else:
                 if val >= threshold: is_trigger = True
            
            status = f"{Colors.FAIL}🔴 {t('trigger')}{Colors.ENDC}" if is_trigger else f"{Colors.GREEN}🟢 {t('pass')}{Colors.ENDC}"
            print(f"  -> Result: {status} (Threshold: {threshold})")
            
            if matches:
                print(f"  -> Sample (Top 10):")
                if rule["type"] in ["bandwidth", "volume"]:
                     matches.sort(key=lambda x: x.get('_metric_val', 0), reverse=True)
                
                for i, m in enumerate(matches[:10]):
                    key = self.get_traffic_details_key(m)
                    print(f"     [{i+1}] {key} Value: {m.get('_metric_fmt')} (PD:{m.get('policy_decision')})")
