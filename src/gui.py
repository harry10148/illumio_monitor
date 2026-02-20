"""
Illumio PCE Monitor — Tkinter GUI (polished ttk themed interface).
Full feature parity with CLI: Dashboard, Rules (add/edit/delete), Settings, Actions (Run, Debug, Test Alert).

Note: On Linux, tkinter requires python3-tk system package:
  Ubuntu/Debian: sudo apt install python3-tk
  RHEL/Rocky:    sudo dnf install python3-tkinter
"""
import re
import datetime
import threading
import logging
import os
import time

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAS_TK = True
except ImportError:
    HAS_TK = False

from src.config import ConfigManager
from src.i18n import t
from src import __version__

logger = logging.getLogger(__name__)

# ─── ANSI Stripping ──────────────────────────────────────────────────────────
_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


# ─── Event Catalog (mirrors settings.py) ─────────────────────────────────────
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

# ─── Color Palette ────────────────────────────────────────────────────────────
BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3d"
FG_TEXT = "#cdd6f4"
FG_DIM = "#6c7086"
ACCENT = "#89b4fa"
ACCENT_HOVER = "#b4d0fb"
SUCCESS = "#a6e3a1"
WARNING = "#f9e2af"
DANGER = "#f38ba8"
BORDER = "#45475a"


def _apply_theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BG_DARK, foreground=FG_TEXT, font=('Segoe UI', 10))
    style.configure('TNotebook', background=BG_DARK, borderwidth=0)
    style.configure('TNotebook.Tab', background=BG_CARD, foreground=FG_TEXT,
                    padding=[16, 8], font=('Segoe UI', 10, 'bold'))
    style.map('TNotebook.Tab', background=[('selected', ACCENT)], foreground=[('selected', BG_DARK)])
    style.configure('TFrame', background=BG_DARK)
    style.configure('Card.TFrame', background=BG_CARD)
    style.configure('TLabel', background=BG_DARK, foreground=FG_TEXT, font=('Segoe UI', 10))
    style.configure('Card.TLabel', background=BG_CARD, foreground=FG_TEXT)
    style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'), foreground=ACCENT, background=BG_DARK)
    style.configure('SubHeader.TLabel', font=('Segoe UI', 11, 'bold'), foreground=FG_TEXT, background=BG_DARK)
    style.configure('Dim.TLabel', foreground=FG_DIM, background=BG_CARD)
    style.configure('Success.TLabel', foreground=SUCCESS, background=BG_CARD)
    style.configure('Danger.TLabel', foreground=DANGER, background=BG_CARD)
    style.configure('TEntry', fieldbackground=BG_CARD, foreground=FG_TEXT,
                    insertcolor=FG_TEXT, bordercolor=BORDER, borderwidth=1)
    style.configure('TButton', background=ACCENT, foreground=BG_DARK,
                    font=('Segoe UI', 10, 'bold'), padding=[12, 6])
    style.map('TButton', background=[('active', ACCENT_HOVER), ('disabled', BORDER)])
    style.configure('Danger.TButton', background=DANGER, foreground=BG_DARK)
    style.map('Danger.TButton', background=[('active', '#f07092')])
    style.configure('Success.TButton', background=SUCCESS, foreground=BG_DARK)
    style.map('Success.TButton', background=[('active', '#b6f3b1')])
    style.configure('Warning.TButton', background=WARNING, foreground=BG_DARK)
    style.map('Warning.TButton', background=[('active', '#fae8bf')])
    style.configure('Treeview', background=BG_CARD, foreground=FG_TEXT,
                    fieldbackground=BG_CARD, borderwidth=0, font=('Segoe UI', 9), rowheight=28)
    style.configure('Treeview.Heading', background=BORDER, foreground=FG_TEXT,
                    font=('Segoe UI', 9, 'bold'))
    style.map('Treeview', background=[('selected', ACCENT)], foreground=[('selected', BG_DARK)])
    style.configure('TCheckbutton', background=BG_CARD, foreground=FG_TEXT)
    style.configure('TCombobox', fieldbackground=BG_CARD, foreground=FG_TEXT, background=BG_CARD)
    style.configure('TLabelframe', background=BG_DARK, foreground=ACCENT, bordercolor=BORDER)
    style.configure('TLabelframe.Label', background=BG_DARK, foreground=ACCENT, font=('Segoe UI', 10, 'bold'))
    style.configure('TRadiobutton', background=BG_DARK, foreground=FG_TEXT)
    style.configure('Card.TRadiobutton', background=BG_CARD, foreground=FG_TEXT)
    style.configure('Card.TCheckbutton', background=BG_CARD, foreground=FG_TEXT)
    style.configure('TSpinbox', fieldbackground=BG_CARD, foreground=FG_TEXT, background=BG_CARD)


def _run_in_thread_with_output(gui, func, done_msg="Completed."):
    """Run func in background thread, capture stdout, strip ANSI, show in action_output."""
    import sys, io

    def worker():
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            func()
        except Exception as e:
            captured.write(f"\nError: {e}\n")
        finally:
            sys.stdout = old_stdout
        output = _strip_ansi(captured.getvalue())
        gui.root.after(0, lambda: gui._action_log(output if output.strip() else done_msg))

    threading.Thread(target=worker, daemon=True).start()


class IllumioGUI:
    def __init__(self, root: tk.Tk, cm: ConfigManager):
        self.root = root
        self.cm = cm
        self.root.title(f"Illumio PCE Monitor v{__version__}")
        self.root.geometry("1000x700")
        self.root.minsize(850, 600)
        self.root.configure(bg=BG_DARK)
        _apply_theme(self.root)

        # Header
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=16, pady=(12, 0))
        ttk.Label(header, text=f"◆ Illumio PCE Monitor v{__version__}", style='Header.TLabel').pack(side='left')
        ttk.Label(header, text=f"API: {self.cm.config['api']['url']}", style='Dim.TLabel').pack(side='right')

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=8)

        self._build_dashboard_tab()
        self._build_rules_tab()
        self._build_settings_tab()
        self._build_actions_tab()

    # ═══════════════════════════════════════════════════════════════════════════
    # Dashboard Tab
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_dashboard_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Dashboard  ")
        cards = ttk.Frame(tab)
        cards.pack(fill='x', padx=8, pady=8)
        self._stat_api = self._make_card(cards, "API Status", "—", 0)
        self._stat_rules = self._make_card(cards, "Active Rules", str(len(self.cm.config['rules'])), 1)
        self._stat_health = self._make_card(cards, "Health Check",
                                            "ON" if self.cm.config['settings'].get('enable_health_check') else "OFF", 2)
        self._stat_lang = self._make_card(cards, "Language",
                                          self.cm.config.get('settings', {}).get('language', 'en').upper(), 3)
        for i in range(4):
            cards.columnconfigure(i, weight=1)

        log_frame = ttk.LabelFrame(tab, text="  Activity Log  ")
        log_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.log_text = scrolledtext.ScrolledText(log_frame, font=('Consolas', 9), bg=BG_CARD, fg=FG_TEXT,
                                                  insertbackground=FG_TEXT, relief='flat', wrap='word', height=12)
        self.log_text.pack(fill='both', expand=True, padx=4, pady=4)
        self._log("Dashboard loaded. Ready.")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="🔗  Test Connection", command=self._test_connection).pack(side='left', padx=4)
        ttk.Button(btn_frame, text="🔄  Refresh", command=self._refresh_dashboard).pack(side='left', padx=4)

    def _make_card(self, parent, title, value, col):
        frame = ttk.Frame(parent, style='Card.TFrame')
        frame.grid(row=0, column=col, padx=4, pady=4, sticky='nsew')
        frame.configure(borderwidth=1, relief='solid')
        ttk.Label(frame, text=title, style='Dim.TLabel', font=('Segoe UI', 9)).pack(pady=(8, 2))
        val_lbl = ttk.Label(frame, text=value, style='Card.TLabel', font=('Segoe UI', 16, 'bold'))
        val_lbl.pack(pady=(0, 8))
        return val_lbl

    def _log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{ts}] {_strip_ansi(msg)}\n")
        self.log_text.see('end')

    def _test_connection(self):
        self._log("Testing PCE connection...")
        def worker():
            from src.api_client import ApiClient
            try:
                api = ApiClient(self.cm)
                status, text = api.check_health()
                clean = _strip_ansi(text)
                if status == 200:
                    self.root.after(0, lambda: self._stat_api.configure(text="Connected", style='Success.TLabel'))
                    self.root.after(0, lambda: self._log(f"✅ PCE connection OK (HTTP {status})"))
                else:
                    self.root.after(0, lambda: self._stat_api.configure(text=f"Error {status}", style='Danger.TLabel'))
                    self.root.after(0, lambda: self._log(f"❌ PCE connection failed: {status} — {clean[:100]}"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"❌ Error: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_dashboard(self):
        self._stat_rules.configure(text=str(len(self.cm.config['rules'])))
        self._stat_health.configure(text="ON" if self.cm.config['settings'].get('enable_health_check') else "OFF")
        self._stat_lang.configure(text=self.cm.config.get('settings', {}).get('language', 'en').upper())
        self._log("Dashboard refreshed.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Rules Tab — View, Add, Delete
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_rules_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Rules  ")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill='x', padx=8, pady=8)
        self._rules_count_label = ttk.Label(toolbar, text=f"Rules ({len(self.cm.config['rules'])} total)",
                                            style='Header.TLabel')
        self._rules_count_label.pack(side='left')
        ttk.Button(toolbar, text="🗑  Delete", style='Danger.TButton',
                   command=self._delete_selected_rule).pack(side='right', padx=4)
        ttk.Button(toolbar, text="📊  + Bandwidth/Volume", style='Warning.TButton',
                   command=self._show_add_bw_vol_dialog).pack(side='right', padx=4)
        ttk.Button(toolbar, text="🚦  + Traffic", style='Warning.TButton',
                   command=self._show_add_traffic_dialog).pack(side='right', padx=4)
        ttk.Button(toolbar, text="📋  + Event", style='Warning.TButton',
                   command=self._show_add_event_dialog).pack(side='right', padx=4)

        cols = ('type', 'name', 'condition', 'filters')
        self.rule_tree = ttk.Treeview(tab, columns=cols, show='headings', height=16)
        self.rule_tree.heading('type', text='Type')
        self.rule_tree.heading('name', text='Name')
        self.rule_tree.heading('condition', text='Condition')
        self.rule_tree.heading('filters', text='Filters')
        self.rule_tree.column('type', width=80)
        self.rule_tree.column('name', width=200)
        self.rule_tree.column('condition', width=200)
        self.rule_tree.column('filters', width=400)

        vsb = ttk.Scrollbar(tab, orient='vertical', command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=vsb.set)
        self.rule_tree.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=(0, 8))
        vsb.pack(side='left', fill='y', pady=(0, 8), padx=(0, 8))

        self._populate_rules()

    def _populate_rules(self):
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        for i, r in enumerate(self.cm.config['rules']):
            rtype = r['type'].capitalize()
            val = r['threshold_count']
            unit = {'volume': ' MB', 'bandwidth': ' Mbps', 'traffic': ' conns'}.get(r['type'], '')
            cond = f"> {val}{unit} (Win:{r.get('threshold_window')}m CD:{r.get('cooldown_minutes', r.get('threshold_window', 10))}m)"
            filters = []
            if r['type'] == 'event':
                filters.append(f"Event: {r.get('filter_value', '')}")
            pd_map = {2: 'Blocked', 1: 'Potential', 0: 'Allowed', -1: 'All'}
            if r.get('pd') is not None and r['type'] in ('traffic', 'bandwidth', 'volume'):
                filters.append(f"PD:{pd_map.get(r['pd'], r['pd'])}")
            if r.get('port'): filters.append(f"Port:{r['port']}")
            if r.get('src_label'): filters.append(f"Src:{r['src_label']}")
            if r.get('dst_label'): filters.append(f"Dst:{r['dst_label']}")
            if r.get('src_ip_in'): filters.append(f"SrcIP:{r['src_ip_in']}")
            if r.get('dst_ip_in'): filters.append(f"DstIP:{r['dst_ip_in']}")
            filter_str = " | ".join(filters) if filters else "—"
            self.rule_tree.insert('', 'end', iid=str(i), values=(rtype, r['name'], cond, filter_str))
        self._rules_count_label.configure(text=f"Rules ({len(self.cm.config['rules'])} total)")

    def _delete_selected_rule(self):
        selected = self.rule_tree.selection()
        if not selected:
            messagebox.showwarning("Delete", "Please select a rule first.")
            return
        if messagebox.askyesno("Confirm", f"Delete {len(selected)} rule(s)?"):
            indices = sorted([int(s) for s in selected], reverse=True)
            self.cm.remove_rules_by_index(indices)
            self._populate_rules()
            self._refresh_dashboard()

    # ─── Add Event Rule Dialog ────────────────────────────────────────────
    def _show_add_event_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Event Rule")
        dlg.geometry("520x500")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Add Event Rule", style='Header.TLabel').pack(padx=12, pady=(12, 4))

        # Category + Event selection
        sel_frame = ttk.LabelFrame(dlg, text="  Event Selection  ")
        sel_frame.pack(fill='x', padx=12, pady=4)

        ttk.Label(sel_frame, text="Category:").pack(anchor='w', padx=8, pady=(4, 0))
        cat_var = tk.StringVar()
        cat_combo = ttk.Combobox(sel_frame, textvariable=cat_var, values=list(FULL_EVENT_CATALOG.keys()),
                                 state='readonly', width=40)
        cat_combo.pack(padx=8, pady=2, anchor='w')

        ttk.Label(sel_frame, text="Event Type:").pack(anchor='w', padx=8, pady=(4, 0))
        evt_var = tk.StringVar()
        evt_combo = ttk.Combobox(sel_frame, textvariable=evt_var, state='readonly', width=50)
        evt_combo.pack(padx=8, pady=(2, 8), anchor='w')

        def on_cat_change(e=None):
            cat = cat_var.get()
            if cat in FULL_EVENT_CATALOG:
                items = [f"{k} ({v})" for k, v in FULL_EVENT_CATALOG[cat].items()]
                evt_combo['values'] = items
                if items:
                    evt_combo.current(0)
        cat_combo.bind('<<ComboboxSelected>>', on_cat_change)

        # Threshold
        th_frame = ttk.LabelFrame(dlg, text="  Threshold  ")
        th_frame.pack(fill='x', padx=12, pady=4)

        th_type_var = tk.StringVar(value="immediate")
        r_row = ttk.Frame(th_frame)
        r_row.pack(fill='x', padx=8, pady=4)
        ttk.Radiobutton(r_row, text="Immediate Alert", variable=th_type_var, value="immediate").pack(side='left', padx=8)
        ttk.Radiobutton(r_row, text="Cumulative Count", variable=th_type_var, value="count").pack(side='left', padx=8)

        count_frame = ttk.Frame(th_frame)
        count_frame.pack(fill='x', padx=8, pady=2)
        ttk.Label(count_frame, text="Count:").pack(side='left')
        count_var = tk.StringVar(value="5")
        ttk.Entry(count_frame, textvariable=count_var, width=8).pack(side='left', padx=4)
        ttk.Label(count_frame, text="Window (min):").pack(side='left', padx=(12, 0))
        win_var = tk.StringVar(value="10")
        ttk.Entry(count_frame, textvariable=win_var, width=8).pack(side='left', padx=4)
        ttk.Label(count_frame, text="Cooldown (min):").pack(side='left', padx=(12, 0))
        cd_var = tk.StringVar(value="10")
        ttk.Entry(count_frame, textvariable=cd_var, width=8).pack(side='left', padx=(4, 8))

        # Health Check toggle
        hc_var = tk.BooleanVar(value=self.cm.config['settings'].get('enable_health_check', True))
        ttk.Checkbutton(dlg, text="Enable PCE Health Check", variable=hc_var).pack(anchor='w', padx=16, pady=4)

        # Buttons
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', padx=12, pady=12)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side='right', padx=4)

        def save():
            cat = cat_var.get()
            evt_sel = evt_var.get()
            if not cat or not evt_sel:
                messagebox.showwarning("Missing", "Please select a category and event.", parent=dlg)
                return
            evt_key = evt_sel.split(" (")[0]
            evt_name = FULL_EVENT_CATALOG.get(cat, {}).get(evt_key, evt_key)
            ttype = th_type_var.get()
            cnt = int(count_var.get() or 1) if ttype == 'count' else 1
            win = int(win_var.get() or 10)
            cd = int(cd_var.get() or win)
            self.cm.config['settings']['enable_health_check'] = hc_var.get()
            self.cm.add_or_update_rule({
                "id": int(datetime.datetime.now().timestamp()),
                "type": "event", "name": evt_name, "filter_key": "event_type", "filter_value": evt_key,
                "desc": evt_name, "rec": "Check Logs", "threshold_type": ttype,
                "threshold_count": cnt, "threshold_window": win, "cooldown_minutes": cd
            })
            self._populate_rules()
            self._refresh_dashboard()
            dlg.destroy()

        ttk.Button(btn_frame, text="💾  Save Rule", style='Success.TButton', command=save).pack(side='right', padx=4)

    # ─── Add Traffic Rule Dialog ──────────────────────────────────────────
    def _show_add_traffic_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Traffic Rule")
        dlg.geometry("560x620")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Add Traffic Rule", style='Header.TLabel').pack(padx=12, pady=(12, 4))

        canvas = tk.Canvas(dlg, bg=BG_DARK, highlightthickness=0)
        vsb = ttk.Scrollbar(dlg, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True, padx=(12, 0), pady=4)
        vsb.pack(side='right', fill='y', padx=(0, 12), pady=4)

        entries = {}

        def _field(parent, label, key, default='', width=40):
            row = ttk.Frame(parent)
            row.pack(fill='x', padx=8, pady=2)
            ttk.Label(row, text=label, width=22, anchor='w').pack(side='left')
            e = ttk.Entry(row, width=width)
            e.insert(0, default)
            e.pack(side='left', fill='x', expand=True)
            entries[key] = e

        # Basic
        basic = ttk.LabelFrame(scroll_frame, text="  Basic  ")
        basic.pack(fill='x', padx=4, pady=4)
        _field(basic, "Rule Name", 'name')

        ttk.Label(basic, text="Policy Decision:").pack(anchor='w', padx=8, pady=(4, 0))
        pd_var = tk.IntVar(value=1)
        pd_row = ttk.Frame(basic)
        pd_row.pack(fill='x', padx=8, pady=2)
        for val, txt in [(1, "Blocked"), (2, "Potential"), (3, "Allowed"), (4, "All")]:
            ttk.Radiobutton(pd_row, text=txt, variable=pd_var, value=val).pack(side='left', padx=6)

        # Filters
        filt = ttk.LabelFrame(scroll_frame, text="  Filters  ")
        filt.pack(fill='x', padx=4, pady=4)
        _field(filt, "Port", 'port')
        ttk.Label(filt, text="Protocol:").pack(anchor='w', padx=8, pady=(4, 0))
        proto_var = tk.IntVar(value=0)
        proto_row = ttk.Frame(filt)
        proto_row.pack(fill='x', padx=8, pady=2)
        for val, txt in [(0, "Both"), (1, "TCP"), (2, "UDP")]:
            ttk.Radiobutton(proto_row, text=txt, variable=proto_var, value=val).pack(side='left', padx=6)
        _field(filt, "Source (Label/IP)", 'src')
        _field(filt, "Destination (Label/IP)", 'dst')

        # Excludes
        excl = ttk.LabelFrame(scroll_frame, text="  Excludes (Optional)  ")
        excl.pack(fill='x', padx=4, pady=4)
        _field(excl, "Exclude Port", 'ex_port')
        _field(excl, "Exclude Source", 'ex_src')
        _field(excl, "Exclude Destination", 'ex_dst')

        # Threshold
        th = ttk.LabelFrame(scroll_frame, text="  Threshold  ")
        th.pack(fill='x', padx=4, pady=4)
        _field(th, "Count Threshold", 'threshold', '10', 8)
        _field(th, "Window (min)", 'window', '10', 8)
        _field(th, "Cooldown (min)", 'cooldown', '10', 8)

        # Buttons
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill='x', padx=4, pady=8)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side='right', padx=4)

        def save():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning("Missing", "Rule name is required.", parent=dlg)
                return
            pd_sel = pd_var.get()
            target_pd = {1: 2, 2: 1, 3: 0, 4: -1}[pd_sel]
            port = entries['port'].get().strip() or None
            if port:
                try: port = int(port)
                except ValueError: port = None
            proto = {1: 6, 2: 17}.get(proto_var.get())
            src = entries['src'].get().strip()
            dst = entries['dst'].get().strip()
            src_label, src_ip = (src, None) if src and '=' in src else (None, src or None)
            dst_label, dst_ip = (dst, None) if dst and '=' in dst else (None, dst or None)

            ex_port = entries['ex_port'].get().strip() or None
            if ex_port:
                try: ex_port = int(ex_port)
                except ValueError: ex_port = None
            ex_src = entries['ex_src'].get().strip()
            ex_dst = entries['ex_dst'].get().strip()
            ex_src_label, ex_src_ip = (ex_src, None) if ex_src and '=' in ex_src else (None, ex_src or None)
            ex_dst_label, ex_dst_ip = (ex_dst, None) if ex_dst and '=' in ex_dst else (None, ex_dst or None)

            cnt = int(entries['threshold'].get() or 10)
            win = int(entries['window'].get() or 10)
            cd = int(entries['cooldown'].get() or win)
            self.cm.add_or_update_rule({
                "id": int(datetime.datetime.now().timestamp()),
                "type": "traffic", "name": name, "pd": target_pd,
                "port": port, "proto": proto,
                "src_label": src_label, "dst_label": dst_label,
                "src_ip_in": src_ip, "dst_ip_in": dst_ip,
                "ex_port": ex_port, "ex_src_label": ex_src_label, "ex_dst_label": ex_dst_label,
                "ex_src_ip": ex_src_ip, "ex_dst_ip": ex_dst_ip,
                "desc": name, "rec": "Check Policy", "threshold_type": "count",
                "threshold_count": cnt, "threshold_window": win, "cooldown_minutes": cd
            })
            self._populate_rules()
            self._refresh_dashboard()
            dlg.destroy()

        ttk.Button(btn_frame, text="💾  Save Rule", style='Success.TButton', command=save).pack(side='right', padx=4)

    # ─── Add Bandwidth/Volume Rule Dialog ─────────────────────────────────
    def _show_add_bw_vol_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Bandwidth / Volume Rule")
        dlg.geometry("560x580")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Add Bandwidth / Volume Rule", style='Header.TLabel').pack(padx=12, pady=(12, 4))

        entries = {}

        def _field(parent, label, key, default='', width=40):
            row = ttk.Frame(parent)
            row.pack(fill='x', padx=8, pady=2)
            ttk.Label(row, text=label, width=22, anchor='w').pack(side='left')
            e = ttk.Entry(row, width=width)
            e.insert(0, default)
            e.pack(side='left', fill='x', expand=True)
            entries[key] = e

        # Basic
        basic = ttk.LabelFrame(dlg, text="  Basic  ")
        basic.pack(fill='x', padx=12, pady=4)
        _field(basic, "Rule Name", 'name')

        ttk.Label(basic, text="Metric Type:").pack(anchor='w', padx=8, pady=(4, 0))
        metric_var = tk.IntVar(value=1)
        m_row = ttk.Frame(basic)
        m_row.pack(fill='x', padx=8, pady=2)
        ttk.Radiobutton(m_row, text="Bandwidth (Mbps, Max)", variable=metric_var, value=1).pack(side='left', padx=6)
        ttk.Radiobutton(m_row, text="Volume (MB, Sum)", variable=metric_var, value=2).pack(side='left', padx=6)

        ttk.Label(basic, text="Policy Decision:").pack(anchor='w', padx=8, pady=(4, 0))
        pd_var = tk.IntVar(value=4)
        pd_row = ttk.Frame(basic)
        pd_row.pack(fill='x', padx=8, pady=2)
        for val, txt in [(1, "Blocked"), (2, "Potential"), (3, "Allowed"), (4, "All")]:
            ttk.Radiobutton(pd_row, text=txt, variable=pd_var, value=val).pack(side='left', padx=6)

        # Filters
        filt = ttk.LabelFrame(dlg, text="  Filters  ")
        filt.pack(fill='x', padx=12, pady=4)
        _field(filt, "Port", 'port')
        _field(filt, "Source (Label/IP)", 'src')
        _field(filt, "Destination (Label/IP)", 'dst')

        # Threshold
        th = ttk.LabelFrame(dlg, text="  Threshold  ")
        th.pack(fill='x', padx=12, pady=4)
        _field(th, "Threshold Value", 'threshold', '100', 8)
        _field(th, "Window (min)", 'window', '10', 8)
        _field(th, "Cooldown (min)", 'cooldown', '30', 8)

        # Buttons
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', padx=12, pady=12)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side='right', padx=4)

        def save():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning("Missing", "Rule name is required.", parent=dlg)
                return
            rtype = "bandwidth" if metric_var.get() == 1 else "volume"
            pd_sel = pd_var.get()
            target_pd = {1: 2, 2: 1, 3: 0, 4: -1}[pd_sel]
            port = entries['port'].get().strip() or None
            if port:
                try: port = int(port)
                except ValueError: port = None
            src = entries['src'].get().strip()
            dst = entries['dst'].get().strip()
            src_label, src_ip = (src, None) if src and '=' in src else (None, src or None)
            dst_label, dst_ip = (dst, None) if dst and '=' in dst else (None, dst or None)
            cnt = float(entries['threshold'].get() or 100)
            win = int(entries['window'].get() or 10)
            cd = int(entries['cooldown'].get() or 30)
            self.cm.add_or_update_rule({
                "id": int(datetime.datetime.now().timestamp()),
                "type": rtype, "name": name, "pd": target_pd,
                "port": port, "proto": None,
                "src_label": src_label, "dst_label": dst_label,
                "src_ip_in": src_ip, "dst_ip_in": dst_ip,
                "desc": name, "rec": "Check Logs", "threshold_type": "count",
                "threshold_count": cnt, "threshold_window": win, "cooldown_minutes": cd
            })
            self._populate_rules()
            self._refresh_dashboard()
            dlg.destroy()

        ttk.Button(btn_frame, text="💾  Save Rule", style='Success.TButton', command=save).pack(side='right', padx=4)

    # ═══════════════════════════════════════════════════════════════════════════
    # Settings Tab
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Settings  ")

        canvas = tk.Canvas(tab, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        scrollbar.pack(side='right', fill='y')

        self._entries = {}

        def _add_field(parent, label, key, default='', show=None):
            row = ttk.Frame(parent)
            row.pack(fill='x', padx=12, pady=3)
            ttk.Label(row, text=label, width=28, anchor='w').pack(side='left')
            entry = ttk.Entry(row, width=48, show=show)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            self._entries[key] = entry

        # API
        api_frame = ttk.LabelFrame(scroll_frame, text="  API Connection  ")
        api_frame.pack(fill='x', padx=4, pady=4)
        _add_field(api_frame, "API URL", 'api_url', self.cm.config['api']['url'])
        _add_field(api_frame, "Org ID", 'api_org', self.cm.config['api']['org_id'])
        _add_field(api_frame, "API Key", 'api_key', self.cm.config['api']['key'])
        _add_field(api_frame, "API Secret", 'api_secret', self.cm.config['api']['secret'], show='*')
        self._ssl_var = tk.BooleanVar(value=self.cm.config['api'].get('verify_ssl', True))
        ttk.Checkbutton(api_frame, text="Verify SSL", variable=self._ssl_var).pack(anchor='w', padx=12, pady=4)

        # Email
        email_frame = ttk.LabelFrame(scroll_frame, text="  Email & SMTP  ")
        email_frame.pack(fill='x', padx=4, pady=4)
        _add_field(email_frame, "Sender", 'email_sender', self.cm.config['email']['sender'])
        _add_field(email_frame, "Recipients (comma)", 'email_rcpt', ', '.join(self.cm.config['email']['recipients']))
        smtp = self.cm.config.get('smtp', {})
        _add_field(email_frame, "SMTP Host", 'smtp_host', smtp.get('host', 'localhost'))
        _add_field(email_frame, "SMTP Port", 'smtp_port', str(smtp.get('port', 25)))
        self._tls_var = tk.BooleanVar(value=smtp.get('enable_tls', False))
        ttk.Checkbutton(email_frame, text="Enable STARTTLS", variable=self._tls_var).pack(anchor='w', padx=12, pady=2)
        self._auth_var = tk.BooleanVar(value=smtp.get('enable_auth', False))
        ttk.Checkbutton(email_frame, text="Enable Auth", variable=self._auth_var).pack(anchor='w', padx=12, pady=2)
        _add_field(email_frame, "SMTP User", 'smtp_user', smtp.get('user', ''))
        _add_field(email_frame, "SMTP Password", 'smtp_pass', smtp.get('password', ''), show='*')

        # Alerts
        alert_frame = ttk.LabelFrame(scroll_frame, text="  Alert Channels  ")
        alert_frame.pack(fill='x', padx=4, pady=4)
        active = self.cm.config.get('alerts', {}).get('active', ['mail'])
        self._mail_var = tk.BooleanVar(value='mail' in active)
        self._line_var = tk.BooleanVar(value='line' in active)
        self._wh_var = tk.BooleanVar(value='webhook' in active)
        ttk.Checkbutton(alert_frame, text="📧  Mail", variable=self._mail_var).pack(anchor='w', padx=12, pady=2)
        ttk.Checkbutton(alert_frame, text="📱  LINE", variable=self._line_var).pack(anchor='w', padx=12, pady=2)
        ttk.Checkbutton(alert_frame, text="🔗  Webhook", variable=self._wh_var).pack(anchor='w', padx=12, pady=2)
        alerts_cfg = self.cm.config.get('alerts', {})
        _add_field(alert_frame, "LINE Token", 'line_token', alerts_cfg.get('line_channel_access_token', ''))
        _add_field(alert_frame, "LINE Target ID", 'line_target', alerts_cfg.get('line_target_id', ''))
        _add_field(alert_frame, "Webhook URL", 'webhook_url', alerts_cfg.get('webhook_url', ''))

        # Language
        lang_frame = ttk.LabelFrame(scroll_frame, text="  Language  ")
        lang_frame.pack(fill='x', padx=4, pady=4)
        self._lang_var = tk.StringVar(value=self.cm.config.get('settings', {}).get('language', 'en'))
        lang_row = ttk.Frame(lang_frame)
        lang_row.pack(fill='x', padx=12, pady=4)
        ttk.Radiobutton(lang_row, text="English", variable=self._lang_var, value="en").pack(side='left', padx=8)
        ttk.Radiobutton(lang_row, text="繁體中文", variable=self._lang_var, value="zh_TW").pack(side='left', padx=8)

        # Save
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill='x', padx=4, pady=8)
        ttk.Button(btn_frame, text="💾  Save All Settings", style='Success.TButton',
                   command=self._save_settings).pack(side='right', padx=8)

    def _save_settings(self):
        try:
            self.cm.config['api']['url'] = self._entries['api_url'].get().strip()
            self.cm.config['api']['org_id'] = self._entries['api_org'].get().strip()
            self.cm.config['api']['key'] = self._entries['api_key'].get().strip()
            secret = self._entries['api_secret'].get().strip()
            if secret:
                self.cm.config['api']['secret'] = secret
            self.cm.config['api']['verify_ssl'] = self._ssl_var.get()
            self.cm.config['email']['sender'] = self._entries['email_sender'].get().strip()
            self.cm.config['email']['recipients'] = [r.strip() for r in self._entries['email_rcpt'].get().split(',') if r.strip()]
            self.cm.config['smtp']['host'] = self._entries['smtp_host'].get().strip()
            self.cm.config['smtp']['port'] = int(self._entries['smtp_port'].get().strip() or 25)
            self.cm.config['smtp']['enable_tls'] = self._tls_var.get()
            self.cm.config['smtp']['enable_auth'] = self._auth_var.get()
            self.cm.config['smtp']['user'] = self._entries['smtp_user'].get().strip()
            smtp_pass = self._entries['smtp_pass'].get().strip()
            if smtp_pass:
                self.cm.config['smtp']['password'] = smtp_pass
            active = []
            if self._mail_var.get(): active.append('mail')
            if self._line_var.get(): active.append('line')
            if self._wh_var.get(): active.append('webhook')
            self.cm.config.setdefault('alerts', {})['active'] = active
            self.cm.config['alerts']['line_channel_access_token'] = self._entries['line_token'].get().strip()
            self.cm.config['alerts']['line_target_id'] = self._entries['line_target'].get().strip()
            self.cm.config['alerts']['webhook_url'] = self._entries['webhook_url'].get().strip()
            self.cm.config.setdefault('settings', {})['language'] = self._lang_var.get()
            self.cm.save()
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Actions Tab — Run Once, Debug, Test Alert, Best Practices
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_actions_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Actions  ")

        ttk.Label(tab, text="Quick Actions", style='Header.TLabel').pack(anchor='w', padx=12, pady=(12, 4))

        btn_container = ttk.Frame(tab)
        btn_container.pack(fill='x', padx=12)

        actions = [
            ("▶  Run Monitor Once", self._action_run_once),
            ("🔍  Traffic Rule Debug Mode", self._action_debug_mode),
            ("📧  Send Test Alert", self._action_test_alert),
            ("📋  Load Best Practices", self._action_best_practices),
        ]
        for text, cmd in actions:
            ttk.Button(btn_container, text=text, command=cmd).pack(fill='x', pady=3)

        # Output
        ttk.Label(tab, text="Output", style='Header.TLabel').pack(anchor='w', padx=12, pady=(12, 4))
        self.action_output = scrolledtext.ScrolledText(tab, font=('Consolas', 9), bg=BG_CARD, fg=FG_TEXT,
                                                       insertbackground=FG_TEXT, relief='flat', wrap='word', height=16)
        self.action_output.pack(fill='both', expand=True, padx=12, pady=(0, 12))

    def _action_log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        clean = _strip_ansi(msg)
        self.action_output.insert('end', f"[{ts}] {clean}\n")
        self.action_output.see('end')

    def _action_run_once(self):
        self._action_log("Starting monitoring cycle...")

        def work():
            from src.api_client import ApiClient
            from src.reporter import Reporter
            from src.analyzer import Analyzer
            api = ApiClient(self.cm)
            rep = Reporter(self.cm)
            ana = Analyzer(self.cm, api, rep)
            ana.run_analysis()
            rep.send_alerts()

        _run_in_thread_with_output(self, work, "✅ Monitoring cycle completed.")
        self.root.after(5000, self._refresh_dashboard)

    def _action_debug_mode(self):
        # Show debug config dialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Traffic Rule Debug Mode")
        dlg.geometry("400x200")
        dlg.configure(bg=BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Debug Mode Settings", style='Header.TLabel').pack(padx=12, pady=(12, 8))

        row1 = ttk.Frame(dlg)
        row1.pack(fill='x', padx=12, pady=4)
        ttk.Label(row1, text="Query Window (min):", width=22).pack(side='left')
        mins_var = tk.StringVar(value="30")
        ttk.Entry(row1, textvariable=mins_var, width=8).pack(side='left')

        row2 = ttk.Frame(dlg)
        row2.pack(fill='x', padx=12, pady=4)
        ttk.Label(row2, text="Policy Decision:", width=22).pack(side='left')
        pd_debug_var = tk.IntVar(value=3)
        for val, txt in [(1, "Blocked"), (2, "Allowed"), (3, "All")]:
            ttk.Radiobutton(row2, text=txt, variable=pd_debug_var, value=val).pack(side='left', padx=4)

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', padx=12, pady=12)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side='right', padx=4)

        def run_debug():
            mins = int(mins_var.get() or 30)
            pd_sel = pd_debug_var.get()
            dlg.destroy()
            self._action_log(f"Running debug mode (window={mins}m, pd={pd_sel})...")

            def work():
                from src.api_client import ApiClient
                from src.reporter import Reporter
                from src.analyzer import Analyzer
                api = ApiClient(self.cm)
                rep = Reporter(self.cm)
                ana = Analyzer(self.cm, api, rep)
                ana.run_debug_mode(mins=mins, pd_sel=pd_sel)

            _run_in_thread_with_output(self, work, "✅ Debug mode completed.")

        ttk.Button(btn_frame, text="🔍  Run Debug", style='Success.TButton', command=run_debug).pack(side='right', padx=4)

    def _action_test_alert(self):
        self._action_log("Sending test alert...")

        def work():
            from src.reporter import Reporter
            Reporter(self.cm).send_alerts(force_test=True)

        _run_in_thread_with_output(self, work, "✅ Test alert dispatched.")

    def _action_best_practices(self):
        if messagebox.askyesno("Confirm", "This will clear all existing rules and load best practices. Continue?"):
            self.cm.load_best_practices()
            self._populate_rules()
            self._refresh_dashboard()
            self._action_log("✅ Best practices loaded.")


def launch_gui(cm: ConfigManager = None):
    """Launch the tkinter GUI. Provides clear error on Linux if python3-tk is missing."""
    if not HAS_TK:
        import platform
        msg = "tkinter is not available.\n"
        if platform.system() == 'Linux':
            msg += "Install it with:\n"
            msg += "  Ubuntu/Debian: sudo apt install python3-tk\n"
            msg += "  RHEL/Rocky:    sudo dnf install python3-tkinter\n"
        else:
            msg += "Reinstall Python with tcl/tk support.\n"
        print(msg)
        return

    if cm is None:
        cm = ConfigManager()
    root = tk.Tk()
    IllumioGUI(root, cm)
    root.mainloop()
