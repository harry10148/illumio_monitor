import os
import datetime
from src.utils import Colors, safe_input
from src.config import ConfigManager
from src.i18n import t, set_language
from src import __version__

FULL_EVENT_CATALOG = {
    "Agent Health": {
        "system_task.agent_missed_heartbeats_check": "遺失心跳",
        "system_task.agent_offline_check": "Agent 離線",
        "lost_agent.found": "重新發現遺失 Agent",
        "agent.service_not_available": "Agent 服務不可用",
        "agent.goodbye": "Agent Goodbye"
    },
    "Agent Security": {
        "agent.tampering": "Agent 遭到竄改",
        "agent.suspend": "Agent 被暫停",
        "agent.clone_detected": "偵測到複製 Agent",
        "agent.activate": "Agent 已配對",
        "agent.deactivate": "Agent 取消配對"
    },
    "User Access": {
        "user.login_failed": "登入失敗",
        "user.sign_in": "使用者登入",
        "user.csrf_validation_failed": "CSRF 驗證失敗"
    },
    "Auth & API": {
        "request.authentication_failed": "API 認證失敗",
        "request.authorization_failed": "API 授權失敗",
        "api_key.create": "建立 API Key",
        "api_key.delete": "刪除 API Key"
    },
    "Policy": {
        "rule_set.delete": "刪除規則集",
        "rule_set.create": "建立規則集",
        "rule_set.update": "更新規則集",
        "sec_rule.create": "建立規則",
        "sec_rule.delete": "刪除規則",
        "sec_policy.create": "政策派送 (Provisioning)"
    },
    "Workloads": {
        "workload.create": "建立工作負載",
        "workload.delete": "刪除工作負載"
    },
    "System": {
        "pce.application_started": "PCE 啟動",
        "cluster.update": "叢集更新"
    }
}

def add_event_menu(cm: ConfigManager, edit_rule=None):
    from src.utils import Colors, safe_input
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        title = t('menu_add_event_title') if not edit_rule else f"=== Modify Event Rule: {edit_rule.get('name', '')} ==="
        print(f"{Colors.HEADER}{title}{Colors.ENDC}")
        print(t('menu_return'))
        if not edit_rule:
            hc = t('ssl_status_on') if cm.config["settings"].get("enable_health_check", True) else t('ssl_status_off')
            print(t('set_health_check', status=hc))
        print("-" * 40)
        cats = list(FULL_EVENT_CATALOG.keys())
        for i, c in enumerate(cats): print(f"{i+1}. {c}")
        sel = input(f"\n{t('select_category')}").strip().upper()
        if sel == '0': break
        if sel == 'H':
            cm.config["settings"]["enable_health_check"] = not cm.config["settings"].get("enable_health_check", True)
            cm.save()
            continue
        if not sel.isdigit() or not (1 <= int(sel) <= len(cats)): continue
        cat = cats[int(sel)-1]
        evts = FULL_EVENT_CATALOG[cat]
        evt_keys = list(evts.keys())
        print(f"\n--- {cat} ---")
        for i, k in enumerate(evt_keys): print(f"{i+1}. {k} ({evts[k]})")
        print(t('menu_cancel'))
        if edit_rule and edit_rule.get('filter_value') in evt_keys:
            def_idx = evt_keys.index(edit_rule['filter_value']) + 1
            ei = safe_input(f"{t('select_event')} [{def_idx}]", int, range(0, len(evt_keys)+1), allow_cancel=True) or def_idx
        else:
            ei = safe_input(t('select_event'), int, range(0, len(evt_keys)+1))
            
        if not ei or ei == 0: continue
        k = evt_keys[ei-1]
        print(f"\n已選擇: {k}")
        print(f"{t('rule_trigger_type_1')}  {t('rule_trigger_type_2')}  {t('menu_cancel')}")
        
        def_ti = 2 if edit_rule and edit_rule.get('threshold_type') == 'count' else 1
        pmpt = f"{t('please_select')} [{def_ti}]" if edit_rule else t('please_select')
        ti = safe_input(pmpt, int, range(0, 3), allow_cancel=True) or (def_ti if edit_rule else None)
        
        if not ti or ti == 0: continue
        ttype, cnt, win = "immediate", 1, 10
        if ti == 2:
            ttype = "count"
            def_cnt = edit_rule.get('threshold_count', 5) if edit_rule else 5
            def_win = edit_rule.get('threshold_window', 10) if edit_rule else 10
            cnt = safe_input(f"{t('cumulative_count')} [{def_cnt}]", int, hint=t('hint_example_5'), allow_cancel=True) or def_cnt
            win = safe_input(f"{t('time_window_mins')} [{def_win}]", int, hint=t('hint_example_10'), allow_cancel=True) or def_win
            
        def_cd = edit_rule.get('cooldown_minutes', win) if edit_rule else win
        cd = safe_input(f"{t('cooldown_mins_default', win=def_cd)} [{def_cd}]", int, allow_cancel=True) or def_cd
        rid = edit_rule.get('id', int(datetime.datetime.now().timestamp())) if edit_rule else int(datetime.datetime.now().timestamp())
        
        cm.add_or_update_rule({
            "id": rid,
            "type": "event", "name": evts[k], "filter_key": "event_type", "filter_value": k,
            "desc": evts[k], "rec": "Check Logs", "threshold_type": ttype, "threshold_count": cnt, 
            "threshold_window": win, "cooldown_minutes": cd
        })
        input(t('rule_saved'))
        break

def add_traffic_menu(cm: ConfigManager, edit_rule=None):
    from src.utils import Colors, safe_input
    
    title = t('menu_add_traffic_title') if not edit_rule else f"=== Modify Traffic Rule: {edit_rule.get('name', '')} ==="
    print(f"\n{Colors.HEADER}{title}{Colors.ENDC}")
    print(t('menu_return'))
    
    def_name = edit_rule.get('name', '') if edit_rule else ''
    name_pmpt = f"{t('rule_name')} [{def_name}]" if def_name else t('rule_name')
    name = safe_input(name_pmpt, str, allow_cancel=True) or def_name
    if not name or name == '0': return
    
    print(t('policy_decision'))
    print(t('pd_1'))
    print(t('pd_2'))
    print(t('pd_3'))
    print(t('pd_4'))
    
    def_pd = 1
    if edit_rule:
        rpd = edit_rule.get('pd', 2)
        if rpd == 2: def_pd = 1
        elif rpd == 1: def_pd = 2
        elif rpd == 0: def_pd = 3
        elif rpd == -1: def_pd = 4
        
    pd_sel = safe_input(f"{t('pd_select_default')} [{def_pd}]", int, range(0, 5), allow_cancel=True) or def_pd
    if pd_sel == 0: return
    if pd_sel == 1: target_pd = 2
    elif pd_sel == 2: target_pd = 1
    elif pd_sel == 3: target_pd = 0
    else: target_pd = -1
    
    print(f"\n{Colors.CYAN}{t('advanced_filters')}{Colors.ENDC}")
    
    def_port = edit_rule.get('port', '') if edit_rule else ''
    port_pmpt = f"{t('port_input')} [{def_port}]" if def_port else t('port_input')
    port_in = safe_input(port_pmpt, int, allow_cancel=True) or (def_port if def_port else None)
    
    proto_in = None
    if port_in:
        def_proto = 0
        if edit_rule and edit_rule.get('proto') == 6: def_proto = 1
        elif edit_rule and edit_rule.get('proto') == 17: def_proto = 2
        p_sel = safe_input(f"{t('proto_select')} [{def_proto}]" if def_proto else t('proto_select'), int, range(0, 3), allow_cancel=True) or def_proto
        if p_sel == 1: proto_in = 6
        elif p_sel == 2: proto_in = 17
        
    def_src = edit_rule.get('src_label', edit_rule.get('src_ip_in', '')) if edit_rule else ''
    src_in = safe_input(f"{t('src_input')} [{def_src}]" if def_src else t('src_input'), str, allow_cancel=True) or def_src
    
    def_dst = edit_rule.get('dst_label', edit_rule.get('dst_ip_in', '')) if edit_rule else ''
    dst_in = safe_input(f"{t('dst_input')} [{def_dst}]" if def_dst else t('dst_input'), str, allow_cancel=True) or def_dst
    
    def_win = edit_rule.get('threshold_window', 10) if edit_rule else 10
    win_pmpt = t('time_window_mins_default_5').replace('5', str(def_win))
    win = safe_input(f"{win_pmpt} [{def_win}]", int, allow_cancel=True) or def_win
    
    def_cnt = edit_rule.get('threshold_count', 10) if edit_rule else 10
    cnt = safe_input(f"{t('trigger_threshold_count')} [{def_cnt}]", int, allow_cancel=True) or def_cnt
    
    def_cd = edit_rule.get('cooldown_minutes', win) if edit_rule else win
    cd = safe_input(f"{t('cooldown_mins_default', win=def_cd)} [{def_cd}]", int, allow_cancel=True) or def_cd
    
    src_label_val, src_ip_val = (src_in, None) if src_in and '=' in src_in else (None, src_in)
    dst_label_val, dst_ip_val = (dst_in, None) if dst_in and '=' in dst_in else (None, dst_in)
    
    print(f"\n{Colors.CYAN}{t('excludes_optional')}{Colors.ENDC}")
    def_ex_port = edit_rule.get('ex_port', '') if edit_rule else ''
    ex_port_in = safe_input(f"{t('ex_port_input')} [{def_ex_port}]" if def_ex_port else t('ex_port_input'), int, allow_cancel=True) or (def_ex_port if def_ex_port else None)
    
    def_ex_src = edit_rule.get('ex_src_label', edit_rule.get('ex_src_ip', '')) if edit_rule else ''
    ex_src_in = safe_input(f"{t('ex_src_input')} [{def_ex_src}]" if def_ex_src else t('ex_src_input'), str, allow_cancel=True) or def_ex_src
    
    def_ex_dst = edit_rule.get('ex_dst_label', edit_rule.get('ex_dst_ip', '')) if edit_rule else ''
    ex_dst_in = safe_input(f"{t('ex_dst_input')} [{def_ex_dst}]" if def_ex_dst else t('ex_dst_input'), str, allow_cancel=True) or def_ex_dst
    
    ex_src_label_val, ex_src_ip_val = (ex_src_in, None) if ex_src_in and '=' in ex_src_in else (None, ex_src_in)
    ex_dst_label_val, ex_dst_ip_val = (ex_dst_in, None) if ex_dst_in and '=' in ex_dst_in else (None, ex_dst_in)
    
    rid = edit_rule.get('id', int(datetime.datetime.now().timestamp())) if edit_rule else int(datetime.datetime.now().timestamp())
    
    cm.add_or_update_rule({
        "id": rid,
        "type": "traffic", "name": name, "pd": target_pd,
        "port": port_in, "proto": proto_in, 
        "src_label": src_label_val, "dst_label": dst_label_val,
        "src_ip_in": src_ip_val, "dst_ip_in": dst_ip_val,
        "ex_port": ex_port_in,
        "ex_src_label": ex_src_label_val, "ex_dst_label": ex_dst_label_val,
        "ex_src_ip": ex_src_ip_val, "ex_dst_ip": ex_dst_ip_val,
        "desc": name, "rec": "Check Policy", "threshold_type": "count", "threshold_count": cnt, 
        "threshold_window": win, "cooldown_minutes": cd
    })
    input(t('traffic_rule_saved'))

def add_bandwidth_volume_menu(cm: ConfigManager, edit_rule=None):
    from src.utils import Colors, safe_input
    
    title = t('menu_add_bw_vol_title') if not edit_rule else f"=== Modify Rule: {edit_rule.get('name', '')} ==="
    print(f"\n{Colors.HEADER}{title}{Colors.ENDC}")
    print(t('menu_return'))
    
    def_name = edit_rule.get('name', '') if edit_rule else ''
    name = safe_input(f"{t('rule_name_bw')} [{def_name}]" if def_name else t('rule_name_bw'), str, allow_cancel=True) or def_name
    if not name or name == '0': return
    
    print(f"\n{Colors.CYAN}{t('step_1_metric')}{Colors.ENDC}")
    print(t('metric_1'))
    print(t('metric_2'))
    
    def_msel = 1 if edit_rule and edit_rule.get('type') == 'bandwidth' else (2 if edit_rule else None)
    m_sel = safe_input(f"{t('please_select')} [{def_msel}]" if def_msel else t('please_select'), int, range(0, 3), allow_cancel=True) or def_msel
    if not m_sel or m_sel == 0: return
    
    rtype = "bandwidth" if m_sel == 1 else "volume"
    unit_prompt = "Mbps" if m_sel == 1 else "MB"
    
    print(f"\n{Colors.CYAN}{t('step_2_filters')}{Colors.ENDC}")
    
    def_port = edit_rule.get('port', '') if edit_rule else ''
    port_in = safe_input(f"{t('port_input')} [{def_port}]" if def_port else t('port_input'), int, allow_cancel=True) or (def_port if def_port else None)
    
    proto_in = None
    if port_in:
        def_proto = 0
        if edit_rule and edit_rule.get('proto') == 6: def_proto = 1
        elif edit_rule and edit_rule.get('proto') == 17: def_proto = 2
        p_sel = safe_input(f"{t('proto_select')} [{def_proto}]" if def_proto else t('proto_select'), int, range(0, 3), allow_cancel=True) or def_proto
        if p_sel == 1: proto_in = 6
        elif p_sel == 2: proto_in = 17
        
    def_src = edit_rule.get('src_label', edit_rule.get('src_ip_in', '')) if edit_rule else ''
    src_in = safe_input(f"{t('src_input')} [{def_src}]" if def_src else t('src_input'), str, allow_cancel=True) or def_src
    
    def_dst = edit_rule.get('dst_label', edit_rule.get('dst_ip_in', '')) if edit_rule else ''
    dst_in = safe_input(f"{t('dst_input')} [{def_dst}]" if def_dst else t('dst_input'), str, allow_cancel=True) or def_dst
    
    src_label_val, src_ip_val = (src_in, None) if src_in and '=' in src_in else (None, src_in)
    dst_label_val, dst_ip_val = (dst_in, None) if dst_in and '=' in dst_in else (None, dst_in)
    
    print(f"\n{Colors.CYAN}{t('step_3_threshold')}{Colors.ENDC}")
    def_th = edit_rule.get('threshold_count', '') if edit_rule else ''
    th = safe_input(f"{t('trigger_threshold_unit', unit=unit_prompt)} [{def_th}]" if def_th else t('trigger_threshold_unit', unit=unit_prompt), float, allow_cancel=True) or def_th
    if not th: return
    
    def_win = edit_rule.get('threshold_window', 5) if edit_rule else 5
    win_pmpt = t('time_window_mins_default_5').replace('5', str(def_win))
    win = safe_input(f"{win_pmpt} [{def_win}]", int, allow_cancel=True) or def_win
    
    def_cd = edit_rule.get('cooldown_minutes', win) if edit_rule else win
    cd = safe_input(f"{t('cooldown_mins_default', win=def_cd)} [{def_cd}]", int, allow_cancel=True) or def_cd
    
    print(f"\n{Colors.CYAN}{t('excludes_optional')}{Colors.ENDC}")
    def_ex_port = edit_rule.get('ex_port', '') if edit_rule else ''
    ex_port_in = safe_input(f"{t('ex_port_input')} [{def_ex_port}]" if def_ex_port else t('ex_port_input'), int, allow_cancel=True) or (def_ex_port if def_ex_port else None)
    
    def_ex_src = edit_rule.get('ex_src_label', edit_rule.get('ex_src_ip', '')) if edit_rule else ''
    ex_src_in = safe_input(f"{t('ex_src_input')} [{def_ex_src}]" if def_ex_src else t('ex_src_input'), str, allow_cancel=True) or def_ex_src
    
    def_ex_dst = edit_rule.get('ex_dst_label', edit_rule.get('ex_dst_ip', '')) if edit_rule else ''
    ex_dst_in = safe_input(f"{t('ex_dst_input')} [{def_ex_dst}]" if def_ex_dst else t('ex_dst_input'), str, allow_cancel=True) or def_ex_dst
    
    ex_src_label_val, ex_src_ip_val = (ex_src_in, None) if ex_src_in and '=' in ex_src_in else (None, ex_src_in)
    ex_dst_label_val, ex_dst_ip_val = (ex_dst_in, None) if ex_dst_in and '=' in ex_dst_in else (None, ex_dst_in)
    
    rid = edit_rule.get('id', int(datetime.datetime.now().timestamp())) if edit_rule else int(datetime.datetime.now().timestamp())
    
    cm.add_or_update_rule({
        "id": rid,
        "type": rtype, "name": name, 
        "port": port_in, "proto": proto_in, 
        "src_label": src_label_val, "dst_label": dst_label_val,
        "src_ip_in": src_ip_val, "dst_ip_in": dst_ip_val,
        "ex_port": ex_port_in,
        "ex_src_label": ex_src_label_val, "ex_dst_label": ex_dst_label_val,
        "ex_src_ip": ex_src_ip_val, "ex_dst_ip": ex_dst_ip_val,
        "threshold_type": "immediate", 
        "threshold_count": th, 
        "threshold_window": win, "cooldown_minutes": cd,
        "desc": f"Alert when {rtype} > {th} {unit_prompt}", "rec": "Check network activity"
    })
    input(t('rule_saved'))

def manage_rules_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}{t('menu_manage_rules_title')}{Colors.ENDC}")
        print(f"{'No.':<4} {'Name':<30} {'Type':<10} {'Condition':<20} {'Filters / Excludes'}")
        print("-" * 100)
        if not cm.config['rules']: print(t('no_rules'))
        for i, r in enumerate(cm.config['rules']):
            rtype = r['type'].capitalize()
            val = r['threshold_count']
            if r['type'] == 'volume': val = f"{val} MB" 
            elif r['type'] == 'bandwidth': val = f"{val} Mbps"
            elif r['type'] == 'traffic': val = f"{val} ({t('table_num_conns')})"
            cond = f"> {val} (Win: {r.get('threshold_window')}m)"
            cd = r.get("cooldown_minutes", r.get("threshold_window", 10))
            cond += f" (CD:{cd}m)"
            filters = []
            if r['type'] == 'traffic':
                pd_map = {2: t('decision_blocked'), 1: t('decision_potential'), 0: t('decision_allowed'), -1: t('pd_4')}
                filters.append(f"[{pd_map.get(r.get('pd', 2), '?')}]")
            if r.get('port'):
                proto_str = "/TCP" if r.get('proto')==6 else "/UDP" if r.get('proto')==17 else ""
                filters.append(f"[Port:{r['port']}{proto_str}]")
            if r.get('src_label'): filters.append(f"[Src:{r['src_label']}]")
            if r.get('dst_label'): filters.append(f"[Dst:{r['dst_label']}]")
            if r.get('src_ip_in'): filters.append(f"[SrcIP:{r['src_ip_in']}]")
            if r.get('dst_ip_in'): filters.append(f"[DstIP:{r['dst_ip_in']}]")
            if r.get('ex_port'): filters.append(f"{Colors.WARNING}[Excl Port:{r['ex_port']}]{Colors.ENDC}")
            if r.get('ex_src_label'): filters.append(f"{Colors.WARNING}[Excl Src:{r['ex_src_label']}]{Colors.ENDC}")
            if r.get('ex_dst_label'): filters.append(f"{Colors.WARNING}[Excl Dst:{r['ex_dst_label']}]{Colors.ENDC}")
            if r.get('ex_src_ip'): filters.append(f"{Colors.WARNING}[Excl SrcIP:{r['ex_src_ip']}]{Colors.ENDC}")
            if r.get('ex_dst_ip'): filters.append(f"{Colors.WARNING}[Excl DstIP:{r['ex_dst_ip']}]{Colors.ENDC}")
            filter_str = " ".join(filters)
            print(f"{i:<4} {r['name'][:28]:<30} {rtype:<10} {cond:<20} {filter_str}")
        val = input(f"\n{t('input_delete_indices')}").strip().lower()
        if val == '-1': break
        
        if val.startswith('d ') or val.startswith('d'):
            val = val[1:].strip()
            try:
                indices = [int(x.strip()) for x in val.split(',')]
                cm.remove_rules_by_index(indices)
                print(t('done'))
            except: pass
        elif val.startswith('m ') or val.startswith('m'):
            val = val[1:].strip()
            try:
                idx = int(val)
                if 0 <= idx < len(cm.config['rules']):
                    rule = cm.config['rules'][idx]
                    print(f"\n{Colors.CYAN}--- Modifying Rule: {rule['name']} ---{Colors.ENDC}")
                    rtype = rule['type']
                    # Pass the edit_rule object. Do NOT remove from rules immediately here.
                    # Wait for successful save in the add_*_methods.
                    cm.remove_rules_by_index([idx])
                    if rtype == 'event':
                        add_event_menu(cm, edit_rule=rule)
                    elif rtype == 'traffic':
                        add_traffic_menu(cm, edit_rule=rule)
                    elif rtype in ['bandwidth', 'volume']:
                        add_bandwidth_volume_menu(cm, edit_rule=rule)
            except Exception as e:
                print(f"Error modifying: {e}")
        else:
            try:
                # Fallback to direct numeric deletion for backwards compatibility
                if val.isdigit() or ',' in val:
                    indices = [int(x.strip()) for x in val.split(',')]
                    cm.remove_rules_by_index(indices)
                    print(t('done'))
            except: pass
        input(t('press_enter_to_continue'))

def alert_settings_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}{t('settings_alert_title')}{Colors.ENDC}")
        
        current_lang = cm.config.get("settings", {}).get("language", "en")
        active_alerts = cm.config.get("alerts", {}).get("active", ["mail"])
        
        mail_status = t('ssl_status_on') if 'mail' in active_alerts else t('ssl_status_off')
        line_status = t('ssl_status_on') if 'line' in active_alerts else t('ssl_status_off')
        webhook_status = t('ssl_status_on') if 'webhook' in active_alerts else t('ssl_status_off')
        
        print(t('change_language', lang=current_lang))
        print(t('toggle_mail_alert', status=mail_status))
        print(t('toggle_line_alert', status=line_status))
        print(t('toggle_webhook_alert', status=webhook_status))
        print(t('edit_line_channel_access_token'))
        print(t('edit_line_target_id'))
        print(t('edit_webhook_url'))
        print(t('menu_return'))
        
        sel = safe_input(f"\n{t('please_select')}", int, range(0, 8))
        if sel == 0: break
        
        if sel == 1:
            lang_sel = safe_input(t('select_language'), int, range(1, 3))
            if lang_sel == 1:
                cm.config.setdefault("settings", {})["language"] = "en"
            elif lang_sel == 2:
                cm.config.setdefault("settings", {})["language"] = "zh_TW"
            cm.save()
            
        elif sel in [2, 3, 4]:
            channel = "mail" if sel == 2 else "line" if sel == 3 else "webhook"
            if channel in active_alerts:
                active_alerts.remove(channel)
            else:
                active_alerts.append(channel)
            cm.config.setdefault("alerts", {})["active"] = active_alerts
            cm.save()
            
        elif sel == 5:
            current_token = cm.config.get("alerts", {}).get("line_channel_access_token", "")
            masked = current_token[:5] + "..." if current_token else t('not_set')
            new_token = safe_input(f"{t('line_token_input')} [{masked}]", str, allow_cancel=True)
            if new_token:
                cm.config.setdefault("alerts", {})["line_channel_access_token"] = new_token
                cm.save()
                
        elif sel == 6:
            current_id = cm.config.get("alerts", {}).get("line_target_id", "")
            masked_id = current_id[:5] + "..." if current_id else t('not_set')
            new_id = safe_input(f"{t('line_target_id_input')} [{masked_id}]", str, allow_cancel=True)
            if new_id:
                cm.config.setdefault("alerts", {})["line_target_id"] = new_id
                cm.save()
                
        elif sel == 7:
            current_url = cm.config.get("alerts", {}).get("webhook_url", "")
            masked = current_url[:15] + "..." if current_url else t('not_set')
            new_url = safe_input(f"{t('webhook_url_input')} [{masked}]", str, allow_cancel=True)
            if new_url:
                cm.config.setdefault("alerts", {})["webhook_url"] = new_url
                cm.save()

def settings_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}{t('menu_settings_title')} v{__version__}{Colors.ENDC}")
        masked_key = cm.config['api']['key'][:5] + "..." if cm.config['api']['key'] else t('not_set')
        print(f"API URL : {cm.config['api']['url']}")
        print(f"API Key : {masked_key}")
        
        alerts_cfg = cm.config.get('alerts', {})
        active = alerts_cfg.get('active', ['mail'])
        channels = []
        if 'mail' in active: channels.append(f"Mail ({cm.config['email']['sender']})")
        if 'line' in active: channels.append("LINE")
        if 'webhook' in active: channels.append("Webhook")
        
        print(f"Alerts  : {', '.join(channels) if channels else t('not_set')}")
        print("-" * 40)
        print(t('settings_1'))
        print(t('settings_2'))
        ssl_status = t('ssl_verify') if cm.config['api'].get('verify_ssl', True) else t('ssl_ignore')
        print(t('settings_3', status=ssl_status))
        smtp_conf = cm.config.get('smtp', {})
        auth_status = f"Auth:{t('ssl_status_on') if smtp_conf.get('enable_auth') else t('ssl_status_off')}"
        print(f"{t('settings_4')} ({smtp_conf.get('host')}:{smtp_conf.get('port')} | {auth_status})")
        print(t('menu_return'))
        sel = safe_input(f"\n{t('please_select')}", int, range(0, 5))
        if sel == 0: break
        if sel == 1:
            new_url = safe_input(f"API URL [{cm.config['api']['url']}]", str, allow_cancel=True)
            if new_url: cm.config['api']['url'] = new_url.strip('"').strip("'")
            
            cm.config['api']['org_id'] = safe_input(f"Org ID [{cm.config['api']['org_id']}]", str, allow_cancel=True) or cm.config['api']['org_id']
            cm.config['api']['key'] = safe_input(f"API Key [{masked_key}]", str, allow_cancel=True) or cm.config['api']['key']
            new_sec = safe_input("API Secret [******]", str, allow_cancel=True)
            if new_sec: cm.config['api']['secret'] = new_sec
            cm.save()
        elif sel == 2:
            alert_settings_menu(cm)
        elif sel == 3:
            current = cm.config['api'].get('verify_ssl', True)
            print(f"{t('settings_3', status=t('ssl_status_on') if current else t('ssl_status_off'))}")
            choice = safe_input(t('change_verify_to'), int, range(1, 3))
            if choice:
                cm.config['api']['verify_ssl'] = (choice == 1)
                cm.save()
        elif sel == 4:
            c = cm.config.get('smtp', {})
            print(f"\n{Colors.CYAN}=== SMTP 設定 ==={Colors.ENDC}")
            c['host'] = safe_input(f"SMTP Host [{c.get('host','localhost')}]", str, allow_cancel=True) or c.get('host','localhost')
            c['port'] = safe_input(f"SMTP Port [{c.get('port', 25)}]", int, allow_cancel=True) or c.get('port', 25)
            
            enable_tls = safe_input(f"啟用 STARTTLS (Y/N/Enter)? [{c.get('enable_tls', False)}]", str, allow_cancel=True)
            if enable_tls and enable_tls.lower() == 'y': c['enable_tls'] = True
            elif enable_tls and enable_tls.lower() == 'n': c['enable_tls'] = False
            
            enable_auth = safe_input(f"啟用驗證 (Y/N/Enter)? [{c.get('enable_auth', False)}]", str, allow_cancel=True)
            if enable_auth and enable_auth.lower() == 'y': c['enable_auth'] = True
            elif enable_auth and enable_auth.lower() == 'n': c['enable_auth'] = False
            
            if c['enable_auth']:
                c['user'] = safe_input(f"Username [{c.get('user','')}]", str, allow_cancel=True) or c.get('user','')
                new_pass = safe_input("Password [******]", str, allow_cancel=True)
                if new_pass: c['password'] = new_pass
            
            cm.config['smtp'] = c
            cm.save()
