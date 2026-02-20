import os
import datetime
from src.utils import Colors, safe_input
from src.config import ConfigManager # Type hint mostly

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

def add_event_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}=== 新增事件監控規則 ==={Colors.ENDC}")
        print("0. 返回上層")
        hc = "ON" if cm.config["settings"].get("enable_health_check", True) else "OFF"
        print(f"H. 設定 PCE Health Check (目前: {hc})")
        print("-" * 40)
        cats = list(FULL_EVENT_CATALOG.keys())
        for i, c in enumerate(cats): print(f"{i+1}. {c}")
        sel = input("\n請選擇類別 (輸入數字，H 設定健檢，0 返回): ").strip().upper()
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
        print("0. 取消")
        ei = safe_input("選擇事件", int, range(0, len(evt_keys)+1))
        if not ei or ei == 0: continue
        k = evt_keys[ei-1]
        print(f"\n已選擇: {k}")
        print("1. 立即告警  2. 累積次數  0. 取消")
        ti = safe_input("選擇", int, range(0, 3))
        if not ti or ti == 0: continue
        ttype, cnt, win = "immediate", 1, 10
        if ti == 2:
            ttype = "count"
            cnt = safe_input("累積次數", int, hint="例: 5") or 5
            win = safe_input("時間窗口(分)", int, hint="例: 10") or 10
        cd = safe_input(f"冷卻時間 (分鐘) [預設: {win}]", int, allow_cancel=True) or win
        cm.add_or_update_rule({
            "id": int(datetime.datetime.now().timestamp()),
            "type": "event", "name": evts[k], "filter_key": "event_type", "filter_value": k,
            "desc": evts[k], "rec": "Check Logs", "threshold_type": ttype, "threshold_count": cnt, 
            "threshold_window": win, "cooldown_minutes": cd
        })
        input("規則已儲存。按 Enter 繼續...")

def add_traffic_menu(cm: ConfigManager):
    print(f"\n{Colors.HEADER}=== 新增流量規則 (Traffic Rule - Blocked/Potential) ==={Colors.ENDC}")
    print("0. 返回上層")
    name = safe_input("規則名稱 (例如: Blocked SSH)", str)
    if not name or name == '0': return
    print("Policy Decision:")
    print("1. Blocked (阻擋)")
    print("2. Potential (潛在阻擋)")
    print("3. Allowed (允許)")
    print("4. All (全部)")
    pd_sel = safe_input("選擇 [預設: 1]", int, range(0, 5), allow_cancel=True)
    if pd_sel == 0: return
    if pd_sel is None: pd_sel = 1
    if pd_sel == 1: target_pd = 2
    elif pd_sel == 2: target_pd = 1
    elif pd_sel == 3: target_pd = 0
    else: target_pd = -1
    print(f"\n{Colors.CYAN}--- 進階過濾 (Advanced Filters) ---{Colors.ENDC}")
    port_in = safe_input("Port (例如: 80, 443) [按 Enter 跳過]", int, allow_cancel=True)
    proto_in = None
    if port_in:
        p_sel = safe_input("協定 (1. TCP, 2. UDP, 0. Both) [預設: Both]", int, range(0, 3), allow_cancel=True)
        if p_sel == 1: proto_in = 6
        elif p_sel == 2: proto_in = 17
    src_in = safe_input("來源標籤/IP/IPList (例如: role=Web 或 10.0.0.1) [按 Enter 跳過]", str, allow_cancel=True)
    dst_in = safe_input("目的標籤/IP/IPList (例如: app=DB 或 192.168.1.1) [按 Enter 跳過]", str, allow_cancel=True)
    
    win = safe_input("時間窗口 (分鐘) [預設: 10]", int, allow_cancel=True) or 10
    cnt = safe_input("觸發閾值 (次數) [預設: 10]", int, allow_cancel=True) or 10
    cd = safe_input(f"冷卻時間 (分鐘) [預設: {win}]", int, allow_cancel=True) or win
    src_label_val, src_ip_val = (src_in, None) if src_in and '=' in src_in else (None, src_in)
    dst_label_val, dst_ip_val = (dst_in, None) if dst_in and '=' in dst_in else (None, dst_in)
    print(f"\n{Colors.CYAN}--- 排除條件 (Excludes) - 選填 ---{Colors.ENDC}")
    ex_port_in = safe_input("排除 Port (例如: 22) [按 Enter 跳過]", int, allow_cancel=True)
    ex_src_in = safe_input("排除來源標籤/IP/IPList (例如: role=Scanner) [按 Enter 跳過]", str, allow_cancel=True)
    ex_dst_in = safe_input("排除目的標籤/IP/IPList (例如: 10.0.0.5) [按 Enter 跳過]", str, allow_cancel=True)
    ex_src_label_val, ex_src_ip_val = (ex_src_in, None) if ex_src_in and '=' in ex_src_in else (None, ex_src_in)
    ex_dst_label_val, ex_dst_ip_val = (ex_dst_in, None) if ex_dst_in and '=' in ex_dst_in else (None, ex_dst_in)
    cm.add_or_update_rule({
        "id": int(datetime.datetime.now().timestamp()),
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
    input("流量規則已新增。按 Enter 繼續...")

def add_bandwidth_volume_menu(cm: ConfigManager):
    print(f"\n{Colors.HEADER}=== 新增頻寬與傳輸量規則 (Bandwidth & Volume) ==={Colors.ENDC}")
    print("0. 返回上層")
    name = safe_input("規則名稱 (例如: Database Spike)", str)
    if not name or name == '0': return
    print(f"\n{Colors.CYAN}--- 1. 選擇監控指標 (Metric) ---{Colors.ENDC}")
    print("1. 頻寬 (Bandwidth) - 適用: 傳輸速率 (Mbps)")
    print("2. 傳輸量 (Total Volume) - 適用: 資料外洩 (MB/GB)")
    m_sel = safe_input("選擇", int, range(0, 3))
    if not m_sel or m_sel == 0: return
    rtype = "bandwidth" if m_sel == 1 else "volume"
    unit_prompt = "Mbps" if m_sel == 1 else "MB"
    print(f"\n{Colors.CYAN}--- 2. 過濾條件 (Filters) ---{Colors.ENDC}")
    port_in = safe_input("Port (例如: 80, 443) [按 Enter 跳過]", int, allow_cancel=True)
    proto_in = None
    if port_in:
        p_sel = safe_input("協定 (1. TCP, 2. UDP, 0. Both) [預設: Both]", int, range(0, 3), allow_cancel=True)
        if p_sel == 1: proto_in = 6
        elif p_sel == 2: proto_in = 17
    src_in = safe_input("來源標籤/IP/IPList (例如: role=Web 或 10.0.0.1) [按 Enter 跳過]", str, allow_cancel=True)
    dst_in = safe_input("目的標籤/IP/IPList (例如: app=DB 或 192.168.1.1) [按 Enter 跳過]", str, allow_cancel=True)
    src_label_val, src_ip_val = (src_in, None) if src_in and '=' in src_in else (None, src_in)
    dst_label_val, dst_ip_val = (dst_in, None) if dst_in and '=' in dst_in else (None, dst_in)
    print(f"\n{Colors.CYAN}--- 3. 閾值設定 (Threshold) ---{Colors.ENDC}")
    th = safe_input(f"觸發閾值 ({unit_prompt})", float)
    if not th: return
    win = safe_input("時間窗口 (分鐘) [預設: 5]", int, allow_cancel=True) or 5
    cd = safe_input(f"冷卻時間 (分鐘) [預設: {win}]", int, allow_cancel=True) or win
    print(f"\n{Colors.CYAN}--- 排除條件 (Excludes) - 選填 ---{Colors.ENDC}")
    ex_port_in = safe_input("排除 Port (例如: 22) [按 Enter 跳過]", int, allow_cancel=True)
    ex_src_in = safe_input("排除來源標籤/IP/IPList (例如: role=Scanner) [按 Enter 跳過]", str, allow_cancel=True)
    ex_dst_in = safe_input("排除目的標籤/IP/IPList (例如: 10.0.0.5) [按 Enter 跳過]", str, allow_cancel=True)
    ex_src_label_val, ex_src_ip_val = (ex_src_in, None) if ex_src_in and '=' in ex_src_in else (None, ex_src_in)
    ex_dst_label_val, ex_dst_ip_val = (ex_dst_in, None) if ex_dst_in and '=' in ex_dst_in else (None, ex_dst_in)
    cm.add_or_update_rule({
        "id": int(datetime.datetime.now().timestamp()),
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
    input("規則已儲存。按 Enter 繼續...")

def manage_rules_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}=== 管理監控規則 ==={Colors.ENDC}")
        print(f"{'No.':<4} {'名稱':<30} {'類型':<10} {'條件':<20} {'過濾 (Filters) / 排除 (Excludes)'}")
        print("-" * 100)
        if not cm.config['rules']: print("(目前沒有規則)")
        for i, r in enumerate(cm.config['rules']):
            rtype = r['type'].capitalize()
            val = r['threshold_count']
            if r['type'] == 'volume': val = f"{val} MB" 
            elif r['type'] == 'bandwidth': val = f"{val} Mbps"
            elif r['type'] == 'traffic': val = f"{val} 次"
            cond = f"> {val} (Window: {r.get('threshold_window')}m)"
            cd = r.get("cooldown_minutes", r.get("threshold_window", 10))
            cond += f" (CD:{cd}m)"
            filters = []
            if r['type'] == 'traffic':
                pd_map = {2: 'Blocked', 1: 'Potential', 0: 'Allowed', -1: 'All'}
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
        val = input("\n輸入編號刪除 (如 0, 2) 或 -1 返回: ")
        if val == '-1': break
        try:
            indices = [int(x.strip()) for x in val.split(',')]
            cm.remove_rules_by_index(indices)
        except: pass
        input("按 Enter 繼續...")

def settings_menu(cm: ConfigManager):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}=== 系統設定 (System Settings) ==={Colors.ENDC}")
        masked_key = cm.config['api']['key'][:5] + "..." if cm.config['api']['key'] else "未設定"
        print(f"API URL : {cm.config['api']['url']}")
        print(f"API Key : {masked_key}")
        print(f"Sender  : {cm.config['email']['sender']}")
        print("-" * 40)
        print("1. 修改 API 設定 (URL, Key, Secret)")
        print("2. 修改 Email 設定 (Sender, Recipients)")
        ssl_status = "驗證 (Verify)" if cm.config['api'].get('verify_ssl', True) else "忽略 (Ignore)"
        print(f"3. SSL 憑證驗證 (目前: {ssl_status})")
        smtp_conf = cm.config.get('smtp', {})
        auth_status = "Auth:ON" if smtp_conf.get('enable_auth') else "Auth:OFF"
        print(f"4. SMTP 設定 ({smtp_conf.get('host')}:{smtp_conf.get('port')} | {auth_status})")
        print("0. 返回")
        sel = safe_input("\n請選擇", int, range(0, 5))
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
            cm.config['email']['sender'] = safe_input(f"Sender [{cm.config['email']['sender']}]", str, allow_cancel=True) or cm.config['email']['sender']
            curr_rcpt = ",".join(cm.config['email']['recipients'])
            new_rcpt = safe_input(f"Recipients [{curr_rcpt}]", str, allow_cancel=True)
            if new_rcpt: cm.config['email']['recipients'] = [x.strip() for x in new_rcpt.split(',')]
            cm.save()
        elif sel == 3:
            current = cm.config['api'].get('verify_ssl', True)
            print(f"目前 SSL 驗證: {'開啟' if current else '關閉'}")
            choice = safe_input("變更為? (1. 開啟 Verify, 2. 關閉 Ignore)", int, range(1, 3))
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
