import datetime
import json
import smtplib
import urllib.request
import urllib.parse
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.utils import Colors
from src.i18n import t

class Reporter:
    def __init__(self, config_manager):
        self.cm = config_manager
        self.health_alerts = []
        self.event_alerts = []
        self.traffic_alerts = []
        self.metric_alerts = []

    def add_health_alert(self, alert):
        self.health_alerts.append(alert)

    def add_event_alert(self, alert):
        self.event_alerts.append(alert)

    def add_traffic_alert(self, alert):
        self.traffic_alerts.append(alert)

    def add_metric_alert(self, alert):
        self.metric_alerts.append(alert)

    def generate_pretty_snapshot_html(self, data_list):
        if not data_list: return "No Data"
        html = "<table style='width:100%; border-collapse:collapse; font-family:Arial,sans-serif; font-size:12px; border:1px solid #ddd;'>"
        html += "<tr style='background-color:#f2f2f2; text-align:left;'>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_value')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_first_seen')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_last_seen')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_dir')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_source')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_destination')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_service')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_num_conns')}</th>"
        html += f"<th style='padding:8px; border:1px solid #ddd;'>{t('table_decision')}</th>"
        html += "</tr>"
        for d in data_list:
            val_str = d.get('_metric_fmt', '-')
            ts_r = d.get('timestamp_range', {})
            t_first = ts_r.get('first_detected', d.get('timestamp','-')).replace('T',' ').split('.')[0]
            t_last = ts_r.get('last_detected', '-').replace('T',' ').split('.')[0]
            
            direction = "IN" if d.get('flow_direction') == 'inbound' else "OUT" if d.get('flow_direction') == 'outbound' else d.get('flow_direction', '-')
            src = d.get('src', {})
            s_ip = src.get('ip', '-')
            s_wl = src.get('workload', {})
            s_name = s_wl.get('name') or s_wl.get('hostname') or s_ip
            s_labels = s_wl.get('labels', [])
            s_badges = "".join([f"<span style='background:#e1ecf4; color:#2c5e77; padding:2px 5px; border-radius:4px; font-size:10px; margin-right:3px;'>{l.get('key')}:{l.get('value')}</span>" for l in s_labels])
            dst = d.get('dst', {})
            d_ip = dst.get('ip', '-')
            d_wl = dst.get('workload', {})
            d_name = d_wl.get('name') or d_wl.get('hostname') or d_ip
            d_labels = d_wl.get('labels', [])
            d_badges = "".join([f"<span style='background:#e1ecf4; color:#2c5e77; padding:2px 5px; border-radius:4px; font-size:10px; margin-right:3px;'>{l.get('key')}:{l.get('value')}</span>" for l in d_labels])
            svc = d.get('service', {})
            port = d.get('dst_port') or svc.get('port') or '-'
            proto = d.get('proto') or svc.get('proto') or '-'
            proto_str = "TCP" if proto == 6 else "UDP" if proto == 17 else str(proto)
            count = d.get('num_connections') or d.get('count') or 1
            pd_map = {
                "blocked": f"<span style='color:white; background:#dc3545; padding:2px 6px; border-radius:3px;'>{t('decision_blocked')}</span>",
                "potentially_blocked": f"<span style='color:black; background:#ffc107; padding:2px 6px; border-radius:3px;'>{t('decision_potential')}</span>",
                "allowed": f"<span style='color:white; background:#28a745; padding:2px 6px; border-radius:3px;'>{t('decision_allowed')}</span>"
            }
            decision = str(d.get('policy_decision')).lower()
            decision_html = pd_map.get(decision, decision)
            html += "<tr>"
            html += f"<td style='padding:8px; border:1px solid #ddd; font-weight:bold; color:#6f42c1;'>{val_str}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd; white-space:nowrap; font-size:10px;'>{t_first}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd; white-space:nowrap; font-size:10px;'>{t_last}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd; text-align:center;'>{direction}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd;'><strong>{s_name}</strong><br><small>{s_ip}</small><br>{s_badges}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd;'><strong>{d_name}</strong><br><small>{d_ip}</small><br>{d_badges}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd;'>{port} / {proto_str}</td>"
            html += f"<td style='padding:8px; border:1px solid #ddd; text-align:center;'><strong>{count}</strong></td>"
            html += f"<td style='padding:8px; border:1px solid #ddd;'>{decision_html}</td>"
            html += "</tr>"
        html += "</table>"
        return html
        
    def _build_plain_text_report(self):
        body = f"{t('report_header')}\n"
        body += f"{t('generated_at', time=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}\n"
        body += "-" * 20 + "\n\n"

        if self.health_alerts:
            body += f"{t('health_alerts_header')}\n"
            for a in self.health_alerts:
                body += f"[{a['time']}] {a['status']} - {a['details']}\n"
            body += "\n"

        if self.event_alerts:
            body += f"{t('security_events_header')}\n"
            for a in self.event_alerts:
                body += f"[{a['time']}] {a['rule']} ({a.get('severity','').upper()} x{a['count']})\n"
                body += f"Desc: {a['desc']}\n"
            body += "\n"

        if self.traffic_alerts:
            body += f"{t('traffic_alerts_header')}\n"
            for a in self.traffic_alerts:
                body += f"- {a['rule']} : {a['count']} ({a.get('criteria','')})\n"
                body += f"  {t('traffic_toptalkers')}: {a['details'].replace('<br>', ', ')}\n"
            body += "\n"

        if self.metric_alerts:
            body += f"{t('metric_alerts_header')}\n"
            for a in self.metric_alerts:
                body += f"- {a['rule']} : {a['count']} ({a.get('criteria','')})\n"
                body += f"  {t('traffic_toptalkers')}: {a['details'].replace('<br>', ', ')}\n"
            body += "\n"
        return body

    def send_alerts(self, force_test=False):
        if not any([self.health_alerts, self.event_alerts, self.traffic_alerts, self.metric_alerts]) and not force_test: return
        
        alerts_config = self.cm.config.get("alerts", {})
        active_channels = alerts_config.get("active", ["mail"])
        
        total_issues = len(self.health_alerts) + len(self.event_alerts) + len(self.traffic_alerts) + len(self.metric_alerts)
        subj = t('mail_subject_test') if force_test else t('mail_subject', count=total_issues)
        
        if "mail" in active_channels:
            self._send_mail(subj)
            
        if "line" in active_channels:
            self._send_line(subj)
            
        if "webhook" in active_channels:
            self._send_webhook(subj)

    def _send_line(self, subj):
        token = self.cm.config.get("alerts", {}).get("line_channel_access_token", "")
        target_id = self.cm.config.get("alerts", {}).get("line_target_id", "")
        if not token or not target_id:
            print(f"{Colors.WARNING}{t('line_config_missing')}{Colors.ENDC}")
            return
            
        message_text = f"{subj}\n\n{self._build_plain_text_report()}"
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "to": target_id,
            "messages": [
                {
                    "type": "text",
                    "text": message_text
                }
            ]
        }
        data = json.dumps(payload).encode("utf-8")
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"{Colors.GREEN}{t('line_alert_sent')}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}{t('line_alert_failed', error='', status=response.status)}{Colors.ENDC}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"{Colors.FAIL}{t('line_alert_failed', error=f'{e} - {error_body}', status=e.code)}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}{t('line_alert_failed', error=e, status='')}{Colors.ENDC}")

    def _send_webhook(self, subj):
        webhook_url = self.cm.config.get("alerts", {}).get("webhook_url", "")
        if not webhook_url:
            print(f"{Colors.WARNING}{t('webhook_url_missing')}{Colors.ENDC}")
            return
            
        payload = {
            "subject": subj,
            "health_alerts": self.health_alerts,
            "event_alerts": self.event_alerts,
            "traffic_alerts": self.traffic_alerts,
            "metric_alerts": self.metric_alerts,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8")
        
        try:
            req = urllib.request.Request(webhook_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                if response.status in [200, 201, 202, 204]:
                    print(f"{Colors.GREEN}{t('webhook_alert_sent')}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}{t('webhook_alert_failed', error='', status=response.status)}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}{t('webhook_alert_failed', error=e, status='')}{Colors.ENDC}")

    def _send_mail(self, subj):
        cfg = self.cm.config["email"]
        if not cfg["recipients"]: 
            print(f"{Colors.WARNING}{t('no_recipients')}{Colors.ENDC}")
            return
        
        style_header = "background-color: #f8f9fa; border-left: 5px solid #007bff; padding: 10px; margin-top: 20px;"
        style_table = "width: 100%; border-collapse: collapse; margin-top: 5px;"
        style_th = "text-align: left; padding: 10px; background-color: #e9ecef; border-bottom: 2px solid #dee2e6;"
        style_td = "padding: 10px; border-bottom: 1px solid #dee2e6;"

        body = f"<html><body style='font-family: Arial, sans-serif; line-height: 1.6; color: #333;'>"
        body += f"<div style='max-width: 950px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px;'>"
        body += f"<h2 style='color: #2c3e50; text-align: center; border-bottom: 2px solid #f60; padding-bottom: 10px;'>{t('report_header')}</h2>"
        body += f"<p style='text-align: center; color: #777; font-size: 12px;'>{t('generated_at', time=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}</p>"

        if self.health_alerts:
            body += f"<div style='{style_header} border-color: #dc3545;'><h3 style='margin:0; color: #dc3545;'>{t('health_alerts_header')}</h3></div>"
            body += f"<table style='{style_table}'><thead><tr><th style='{style_th}'>{t('health_time')}</th><th style='{style_th}'>{t('health_status')}</th><th style='{style_th}'>{t('health_details')}</th></tr></thead><tbody>"
            for a in self.health_alerts:
                body += f"<tr><td style='{style_td}'>{a['time']}</td><td style='{style_td} color: red; font-weight: bold;'>{a['status']}</td><td style='{style_td}'>{a['details']}</td></tr>"
            body += "</tbody></table>"

        if self.event_alerts:
            body += f"<div style='{style_header} border-color: #ffc107;'><h3 style='margin:0; color: #d39e00;'>{t('security_events_header')}</h3></div>"
            body += f"<table style='{style_table}'><thead><tr><th style='{style_th}'>{t('event_time')}</th><th style='{style_th}'>{t('event_name')}</th><th style='{style_th}'>{t('event_severity')}</th><th style='{style_th}'>{t('event_source')}</th></tr></thead><tbody>"
            for a in self.event_alerts:
                sev_color = "red" if a.get('severity')=='error' else "orange"
                body += f"<tr><td style='{style_td}'>{a['time']}</td><td style='{style_td}'><strong>{a['rule']}</strong><br><small>{a['desc']}</small></td><td style='{style_td} color:{sev_color}'>{a.get('severity','').upper()} ({a['count']})</td><td style='{style_td}'>{a['source']}</td></tr>"
                if a.get('raw_data'):
                    body += f"<tr><td colspan='4' style='padding: 10px; background-color: #f8f9fa;'><div style='font-size: 11px; color: #666; margin-bottom: 5px;'>{t('raw_snapshot')}</div><pre style='background: #eee; padding: 5px; border-radius: 3px; font-size: 10px; overflow-x: auto;'>{json.dumps(a['raw_data'], indent=2)}</pre></td></tr>"
            body += "</tbody></table>"

        if self.traffic_alerts:
            body += f"<div style='{style_header} border-color: #17a2b8;'><h3 style='margin:0; color: #117a8b;'>{t('traffic_alerts_header')}</h3></div>"
            body += f"<table style='{style_table}'><thead><tr><th style='{style_th}'>{t('traffic_rule')}</th><th style='{style_th}'>{t('traffic_count')}</th><th style='{style_th}'>{t('traffic_criteria')}</th><th style='{style_th}'>{t('traffic_toptalkers')}</th></tr></thead><tbody>"
            for a in self.traffic_alerts:
                body += f"<tr><td style='{style_td}'><strong>{a['rule']}</strong></td><td style='{style_td} font-size: 16px; font-weight: bold; color: #d9534f;'>{a['count']}</td><td style='{style_td} font-size:11px; color:#555;'>{a.get('criteria','')}</td><td style='{style_td} font-size: 12px;'>{a['details']}</td></tr>"
                body += f"<tr><td colspan='4' style='padding: 15px; background-color: #fff;'>{self.generate_pretty_snapshot_html(a.get('raw_data', []))}</td></tr>"
            body += "</tbody></table>"

        if self.metric_alerts:
            body += f"<div style='{style_header} border-color: #6f42c1;'><h3 style='margin:0; color: #5a32a3;'>{t('metric_alerts_header')}</h3></div>"
            body += f"<table style='{style_table}'><thead><tr><th style='{style_th}'>{t('traffic_rule')}</th><th style='{style_th}'>{t('table_value')}</th><th style='{style_th}'>{t('traffic_criteria')}</th><th style='{style_th}'>{t('traffic_toptalkers')}</th></tr></thead><tbody>"
            for a in self.metric_alerts:
                body += f"<tr><td style='{style_td}'><strong>{a['rule']}</strong></td><td style='{style_td} font-size: 16px; font-weight: bold; color: #6f42c1;'>{a['count']}</td><td style='{style_td} font-size:11px; color:#555;'>{a.get('criteria','')}</td><td style='{style_td} font-size: 12px;'>{a['details']}</td></tr>"
                body += f"<tr><td colspan='4' style='padding: 15px; background-color: #fff;'>{self.generate_pretty_snapshot_html(a.get('raw_data', []))}</td></tr>"
            body += "</tbody></table>"

        body += "</div></body></html>"

        msg = MIMEMultipart()
        msg['Subject'] = subj
        msg['From'] = cfg['sender']
        msg['To'] = ",".join(cfg['recipients'])
        msg.attach(MIMEText(body, 'html'))
        try:
            smtp_conf = self.cm.config.get('smtp', {})
            host = smtp_conf.get('host', 'localhost')
            port = int(smtp_conf.get('port', 25))
            
            s = smtplib.SMTP(host, port)
            s.ehlo()
            if smtp_conf.get('enable_tls'):
                s.starttls()
                s.ehlo()
            
            if smtp_conf.get('enable_auth'):
                s.login(smtp_conf.get('user'), smtp_conf.get('password'))
            
            s.sendmail(cfg['sender'], cfg['recipients'], msg.as_string())
            s.quit()
            print(f"{Colors.GREEN}{t('mail_sent', host=host, port=port)}{Colors.ENDC}")
        except Exception as e: print(f"{Colors.FAIL}{t('mail_failed', error=e)}{Colors.ENDC}")
