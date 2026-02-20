"""
Illumio PCE Monitor — Tkinter GUI (polished ttk themed interface).
Provides Dashboard, Rules, Settings, and Actions tabs.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
import datetime
import os

from src.config import ConfigManager
from src.api_client import ApiClient
from src.reporter import Reporter
from src.analyzer import Analyzer
from src.i18n import t
from src import __version__

logger = logging.getLogger(__name__)

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
    """Configure ttk style for a polished dark theme."""
    style = ttk.Style(root)
    style.theme_use('clam')

    style.configure('.', background=BG_DARK, foreground=FG_TEXT,
                    font=('Segoe UI', 10))
    style.configure('TNotebook', background=BG_DARK, borderwidth=0)
    style.configure('TNotebook.Tab', background=BG_CARD, foreground=FG_TEXT,
                    padding=[16, 8], font=('Segoe UI', 10, 'bold'))
    style.map('TNotebook.Tab',
              background=[('selected', ACCENT)],
              foreground=[('selected', BG_DARK)])

    style.configure('TFrame', background=BG_DARK)
    style.configure('Card.TFrame', background=BG_CARD)
    style.configure('TLabel', background=BG_DARK, foreground=FG_TEXT,
                    font=('Segoe UI', 10))
    style.configure('Card.TLabel', background=BG_CARD, foreground=FG_TEXT)
    style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'),
                    foreground=ACCENT, background=BG_DARK)
    style.configure('Dim.TLabel', foreground=FG_DIM, background=BG_CARD)
    style.configure('Success.TLabel', foreground=SUCCESS, background=BG_CARD)
    style.configure('Danger.TLabel', foreground=DANGER, background=BG_CARD)

    style.configure('TEntry', fieldbackground=BG_CARD, foreground=FG_TEXT,
                    insertcolor=FG_TEXT, bordercolor=BORDER, borderwidth=1)
    style.configure('TButton', background=ACCENT, foreground=BG_DARK,
                    font=('Segoe UI', 10, 'bold'), padding=[12, 6])
    style.map('TButton',
              background=[('active', ACCENT_HOVER), ('disabled', BORDER)])

    style.configure('Danger.TButton', background=DANGER, foreground=BG_DARK)
    style.map('Danger.TButton', background=[('active', '#f07092')])
    style.configure('Success.TButton', background=SUCCESS, foreground=BG_DARK)
    style.map('Success.TButton', background=[('active', '#b6f3b1')])

    style.configure('Treeview', background=BG_CARD, foreground=FG_TEXT,
                    fieldbackground=BG_CARD, borderwidth=0,
                    font=('Segoe UI', 9), rowheight=28)
    style.configure('Treeview.Heading', background=BORDER, foreground=FG_TEXT,
                    font=('Segoe UI', 9, 'bold'))
    style.map('Treeview', background=[('selected', ACCENT)],
              foreground=[('selected', BG_DARK)])

    style.configure('TCheckbutton', background=BG_CARD, foreground=FG_TEXT)
    style.configure('TCombobox', fieldbackground=BG_CARD, foreground=FG_TEXT,
                    background=BG_CARD)

    style.configure('TLabelframe', background=BG_DARK, foreground=ACCENT,
                    bordercolor=BORDER)
    style.configure('TLabelframe.Label', background=BG_DARK, foreground=ACCENT,
                    font=('Segoe UI', 10, 'bold'))


class IllumioGUI:
    def __init__(self, root: tk.Tk, cm: ConfigManager):
        self.root = root
        self.cm = cm
        self.root.title(f"Illumio PCE Monitor v{__version__}")
        self.root.geometry("960x640")
        self.root.minsize(800, 550)
        self.root.configure(bg=BG_DARK)

        # Set window icon if available
        try:
            self.root.iconbitmap(default='')
        except tk.TclError:
            pass

        _apply_theme(self.root)

        # Header
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=16, pady=(12, 0))
        ttk.Label(header, text=f"◆ Illumio PCE Monitor v{__version__}",
                  style='Header.TLabel').pack(side='left')
        ttk.Label(header, text=f"API: {self.cm.config['api']['url']}",
                  style='Dim.TLabel').pack(side='right')

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=8)

        self._build_dashboard_tab()
        self._build_rules_tab()
        self._build_settings_tab()
        self._build_actions_tab()

    # ─── Dashboard Tab ────────────────────────────────────────────────────

    def _build_dashboard_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Dashboard  ")

        # Stats cards row
        cards = ttk.Frame(tab)
        cards.pack(fill='x', padx=8, pady=8)

        self._stat_api = self._make_card(cards, "API Status", "—", 0)
        self._stat_rules = self._make_card(cards, "Active Rules",
                                           str(len(self.cm.config['rules'])), 1)
        self._stat_health = self._make_card(cards, "Health Check",
                                            "ON" if self.cm.config['settings'].get('enable_health_check') else "OFF", 2)
        self._stat_lang = self._make_card(cards, "Language",
                                          self.cm.config.get('settings', {}).get('language', 'en').upper(), 3)

        for i in range(4):
            cards.columnconfigure(i, weight=1)

        # Log area
        log_frame = ttk.LabelFrame(tab, text="  Activity Log  ")
        log_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=('Consolas', 9), bg=BG_CARD, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief='flat', wrap='word', height=12
        )
        self.log_text.pack(fill='both', expand=True, padx=4, pady=4)
        self._log("Dashboard loaded. Ready.")

        # Test connection button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="🔗  Test Connection",
                   command=self._test_connection).pack(side='left', padx=4)
        ttk.Button(btn_frame, text="🔄  Refresh",
                   command=self._refresh_dashboard).pack(side='left', padx=4)

    def _make_card(self, parent, title, value, col):
        frame = ttk.Frame(parent, style='Card.TFrame')
        frame.grid(row=0, column=col, padx=4, pady=4, sticky='nsew')
        frame.configure(borderwidth=1, relief='solid')
        ttk.Label(frame, text=title, style='Dim.TLabel',
                  font=('Segoe UI', 9)).pack(pady=(8, 2))
        val_lbl = ttk.Label(frame, text=value, style='Card.TLabel',
                            font=('Segoe UI', 16, 'bold'))
        val_lbl.pack(pady=(0, 8))
        return val_lbl

    def _log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{ts}] {msg}\n")
        self.log_text.see('end')

    def _test_connection(self):
        self._log("Testing PCE connection...")

        def worker():
            try:
                api = ApiClient(self.cm)
                status, text = api.check_health()
                if status == 200:
                    self.root.after(0, lambda: self._stat_api.configure(
                        text="Connected", style='Success.TLabel'))
                    self.root.after(0, lambda: self._log(
                        f"✅ PCE connection OK (HTTP {status})"))
                else:
                    self.root.after(0, lambda: self._stat_api.configure(
                        text=f"Error {status}", style='Danger.TLabel'))
                    self.root.after(0, lambda: self._log(
                        f"❌ PCE connection failed: {status} — {text[:100]}"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"❌ Error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_dashboard(self):
        self._stat_rules.configure(text=str(len(self.cm.config['rules'])))
        self._stat_health.configure(
            text="ON" if self.cm.config['settings'].get('enable_health_check') else "OFF")
        self._stat_lang.configure(
            text=self.cm.config.get('settings', {}).get('language', 'en').upper())
        self._log("Dashboard refreshed.")

    # ─── Rules Tab ────────────────────────────────────────────────────────

    def _build_rules_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Rules  ")

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill='x', padx=8, pady=8)
        ttk.Label(toolbar, text=f"Rules ({len(self.cm.config['rules'])} total)",
                  style='Header.TLabel').pack(side='left')
        ttk.Button(toolbar, text="🗑  Delete", style='Danger.TButton',
                   command=self._delete_selected_rule).pack(side='right', padx=4)

        # Treeview
        cols = ('type', 'name', 'condition', 'filters')
        self.rule_tree = ttk.Treeview(tab, columns=cols, show='headings', height=16)
        self.rule_tree.heading('type', text='Type')
        self.rule_tree.heading('name', text='Name')
        self.rule_tree.heading('condition', text='Condition')
        self.rule_tree.heading('filters', text='Filters')
        self.rule_tree.column('type', width=80)
        self.rule_tree.column('name', width=200)
        self.rule_tree.column('condition', width=200)
        self.rule_tree.column('filters', width=350)
        self.rule_tree.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        scrollbar = ttk.Scrollbar(tab, orient='vertical',
                                  command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=scrollbar.set)

        self._populate_rules()

    def _populate_rules(self):
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)

        for i, r in enumerate(self.cm.config['rules']):
            rtype = r['type'].capitalize()
            val = r['threshold_count']
            if r['type'] == 'volume':
                val = f"{val} MB"
            elif r['type'] == 'bandwidth':
                val = f"{val} Mbps"
            elif r['type'] == 'traffic':
                val = f"{val} conns"
            cond = f"> {val} (Win: {r.get('threshold_window')}m, CD: {r.get('cooldown_minutes', r.get('threshold_window', 10))}m)"

            filters = []
            if r['type'] == 'event':
                filters.append(f"Event: {r.get('filter_value', '')}")
            if r.get('port'):
                filters.append(f"Port:{r['port']}")
            if r.get('src_label'):
                filters.append(f"Src:{r['src_label']}")
            if r.get('dst_label'):
                filters.append(f"Dst:{r['dst_label']}")
            filter_str = " | ".join(filters) if filters else "—"

            self.rule_tree.insert('', 'end', iid=str(i),
                                 values=(rtype, r['name'], cond, filter_str))

    def _delete_selected_rule(self):
        selected = self.rule_tree.selection()
        if not selected:
            messagebox.showwarning("Delete", "Please select a rule first.")
            return
        if messagebox.askyesno("Confirm", f"Delete {len(selected)} rule(s)?"):
            indices = sorted([int(s) for s in selected], reverse=True)
            self.cm.remove_rules_by_index(indices)
            self._populate_rules()

    # ─── Settings Tab ─────────────────────────────────────────────────────

    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Settings  ")

        canvas = tk.Canvas(tab, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        scrollbar.pack(side='right', fill='y')

        # API Section
        api_frame = ttk.LabelFrame(scroll_frame, text="  API Connection  ")
        api_frame.pack(fill='x', padx=4, pady=4)
        self._entries = {}
        self._add_field(api_frame, "API URL", 'api_url',
                        self.cm.config['api']['url'])
        self._add_field(api_frame, "Org ID", 'api_org',
                        self.cm.config['api']['org_id'])
        self._add_field(api_frame, "API Key", 'api_key',
                        self.cm.config['api']['key'])
        self._add_field(api_frame, "API Secret", 'api_secret',
                        self.cm.config['api']['secret'], show='*')

        self._ssl_var = tk.BooleanVar(value=self.cm.config['api'].get('verify_ssl', True))
        ttk.Checkbutton(api_frame, text="Verify SSL",
                        variable=self._ssl_var).pack(anchor='w', padx=12, pady=4)

        # Email / SMTP Section
        email_frame = ttk.LabelFrame(scroll_frame, text="  Email & SMTP  ")
        email_frame.pack(fill='x', padx=4, pady=4)
        self._add_field(email_frame, "Sender", 'email_sender',
                        self.cm.config['email']['sender'])
        self._add_field(email_frame, "Recipients (comma-separated)", 'email_rcpt',
                        ', '.join(self.cm.config['email']['recipients']))

        smtp = self.cm.config.get('smtp', {})
        self._add_field(email_frame, "SMTP Host", 'smtp_host',
                        smtp.get('host', 'localhost'))
        self._add_field(email_frame, "SMTP Port", 'smtp_port',
                        str(smtp.get('port', 25)))
        self._tls_var = tk.BooleanVar(value=smtp.get('enable_tls', False))
        ttk.Checkbutton(email_frame, text="Enable STARTTLS",
                        variable=self._tls_var).pack(anchor='w', padx=12, pady=2)
        self._auth_var = tk.BooleanVar(value=smtp.get('enable_auth', False))
        ttk.Checkbutton(email_frame, text="Enable Auth",
                        variable=self._auth_var).pack(anchor='w', padx=12, pady=2)
        self._add_field(email_frame, "SMTP User", 'smtp_user',
                        smtp.get('user', ''))
        self._add_field(email_frame, "SMTP Password", 'smtp_pass',
                        smtp.get('password', ''), show='*')

        # Alert Channels
        alert_frame = ttk.LabelFrame(scroll_frame, text="  Alert Channels  ")
        alert_frame.pack(fill='x', padx=4, pady=4)
        active = self.cm.config.get('alerts', {}).get('active', ['mail'])
        self._mail_var = tk.BooleanVar(value='mail' in active)
        self._line_var = tk.BooleanVar(value='line' in active)
        self._wh_var = tk.BooleanVar(value='webhook' in active)
        ttk.Checkbutton(alert_frame, text="📧  Mail",
                        variable=self._mail_var).pack(anchor='w', padx=12, pady=2)
        ttk.Checkbutton(alert_frame, text="📱  LINE",
                        variable=self._line_var).pack(anchor='w', padx=12, pady=2)
        ttk.Checkbutton(alert_frame, text="🔗  Webhook",
                        variable=self._wh_var).pack(anchor='w', padx=12, pady=2)

        alerts_cfg = self.cm.config.get('alerts', {})
        self._add_field(alert_frame, "LINE Token", 'line_token',
                        alerts_cfg.get('line_channel_access_token', ''))
        self._add_field(alert_frame, "LINE Target ID", 'line_target',
                        alerts_cfg.get('line_target_id', ''))
        self._add_field(alert_frame, "Webhook URL", 'webhook_url',
                        alerts_cfg.get('webhook_url', ''))

        # Language
        lang_frame = ttk.LabelFrame(scroll_frame, text="  Language  ")
        lang_frame.pack(fill='x', padx=4, pady=4)
        self._lang_var = tk.StringVar(
            value=self.cm.config.get('settings', {}).get('language', 'en'))
        lang_row = ttk.Frame(lang_frame)
        lang_row.pack(fill='x', padx=12, pady=4)
        ttk.Radiobutton(lang_row, text="English", variable=self._lang_var,
                        value="en").pack(side='left', padx=8)
        ttk.Radiobutton(lang_row, text="繁體中文", variable=self._lang_var,
                        value="zh_TW").pack(side='left', padx=8)

        # Save button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill='x', padx=4, pady=8)
        ttk.Button(btn_frame, text="💾  Save All Settings", style='Success.TButton',
                   command=self._save_settings).pack(side='right', padx=8)

    def _add_field(self, parent, label, key, default='', show=None):
        row = ttk.Frame(parent)
        row.pack(fill='x', padx=12, pady=3)
        ttk.Label(row, text=label, width=28, anchor='w').pack(side='left')
        entry = ttk.Entry(row, width=48, show=show)
        entry.insert(0, default)
        entry.pack(side='left', fill='x', expand=True)
        self._entries[key] = entry

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
            self.cm.config['email']['recipients'] = [
                r.strip() for r in self._entries['email_rcpt'].get().split(',') if r.strip()
            ]

            self.cm.config['smtp']['host'] = self._entries['smtp_host'].get().strip()
            self.cm.config['smtp']['port'] = int(self._entries['smtp_port'].get().strip() or 25)
            self.cm.config['smtp']['enable_tls'] = self._tls_var.get()
            self.cm.config['smtp']['enable_auth'] = self._auth_var.get()
            self.cm.config['smtp']['user'] = self._entries['smtp_user'].get().strip()
            smtp_pass = self._entries['smtp_pass'].get().strip()
            if smtp_pass:
                self.cm.config['smtp']['password'] = smtp_pass

            active = []
            if self._mail_var.get():
                active.append('mail')
            if self._line_var.get():
                active.append('line')
            if self._wh_var.get():
                active.append('webhook')
            self.cm.config.setdefault('alerts', {})['active'] = active
            self.cm.config['alerts']['line_channel_access_token'] = \
                self._entries['line_token'].get().strip()
            self.cm.config['alerts']['line_target_id'] = \
                self._entries['line_target'].get().strip()
            self.cm.config['alerts']['webhook_url'] = \
                self._entries['webhook_url'].get().strip()

            self.cm.config.setdefault('settings', {})['language'] = self._lang_var.get()

            self.cm.save()
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    # ─── Actions Tab ──────────────────────────────────────────────────────

    def _build_actions_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Actions  ")

        ttk.Label(tab, text="Quick Actions", style='Header.TLabel').pack(
            anchor='w', padx=12, pady=(12, 4))
        ttk.Label(tab, text="Run monitoring tasks and send alerts",
                  style='Dim.TLabel').pack(anchor='w', padx=12, pady=(0, 12))

        btn_container = ttk.Frame(tab)
        btn_container.pack(fill='x', padx=12)

        actions = [
            ("▶  Run Monitor Once", self._action_run_once),
            ("📧  Send Test Alert", self._action_test_alert),
            ("📋  Load Best Practices", self._action_best_practices),
        ]

        for text, cmd in actions:
            btn = ttk.Button(btn_container, text=text, command=cmd)
            btn.pack(fill='x', pady=4)

        # Output area
        ttk.Label(tab, text="Output", style='Header.TLabel').pack(
            anchor='w', padx=12, pady=(16, 4))
        self.action_output = scrolledtext.ScrolledText(
            tab, font=('Consolas', 9), bg=BG_CARD, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief='flat', wrap='word', height=14
        )
        self.action_output.pack(fill='both', expand=True, padx=12, pady=(0, 12))

    def _action_log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.action_output.insert('end', f"[{ts}] {msg}\n")
        self.action_output.see('end')

    def _action_run_once(self):
        self._action_log("Starting monitoring cycle...")

        def worker():
            import sys
            import io
            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                api = ApiClient(self.cm)
                rep = Reporter(self.cm)
                ana = Analyzer(self.cm, api, rep)
                ana.run_analysis()
                rep.send_alerts()
            except Exception as e:
                captured.write(f"\nError: {e}\n")
            finally:
                sys.stdout = old_stdout
            output = captured.getvalue()
            self.root.after(0, lambda: self._action_log(output if output else "Completed."))
            self.root.after(0, self._refresh_dashboard)

        threading.Thread(target=worker, daemon=True).start()

    def _action_test_alert(self):
        self._action_log("Sending test alert...")

        def worker():
            try:
                Reporter(self.cm).send_alerts(force_test=True)
                self.root.after(0, lambda: self._action_log("✅ Test alert dispatched."))
            except Exception as e:
                self.root.after(0, lambda: self._action_log(f"❌ Error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _action_best_practices(self):
        if messagebox.askyesno("Confirm", "This will clear all existing rules and load best practices. Continue?"):
            self.cm.load_best_practices()
            self._populate_rules()
            self._refresh_dashboard()
            self._action_log("✅ Best practices loaded.")


def launch_gui(cm: ConfigManager = None):
    """Launch the tkinter GUI. Can be called from console menu or --gui flag."""
    if cm is None:
        cm = ConfigManager()
    root = tk.Tk()
    IllumioGUI(root, cm)
    root.mainloop()
