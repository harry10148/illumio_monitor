import requests
import json
import time
import gzip
from io import BytesIO
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from src.utils import Colors

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

MAX_TRAFFIC_RESULTS = 200000

class ApiClient:
    def __init__(self, config_manager):
        self.cm = config_manager
        self.api_cfg = self.cm.config["api"]
        self.base_url = f"{self.api_cfg['url']}/api/v2/orgs/{self.api_cfg['org_id']}"
        self.auth = HTTPBasicAuth(self.api_cfg['key'], self.api_cfg['secret'])
        self.verify_ssl = self.api_cfg['verify_ssl']

    def check_health(self):
        url = f"{self.api_cfg['url']}/api/v2/health"
        try:
            r = requests.get(url, auth=self.auth, verify=self.verify_ssl, timeout=10)
            return r.status_code, r.text
        except Exception as e:
            return 0, str(e)

    def fetch_events(self, start_time_str, max_results=1000):
        try:
            params = {"timestamp[gte]": start_time_str, "max_results": max_results}
            headers = {"Accept": "application/json"}
            r = requests.get(f"{self.base_url}/events", auth=self.auth, headers=headers, params=params, verify=self.verify_ssl, timeout=15)
            if r.status_code != 200:
                print(f"{Colors.FAIL}Get Events Failed: {r.status_code}{Colors.ENDC}")
                return []
            return r.json()
        except Exception as e:
            print(f"{Colors.FAIL}Fetch Events Error: {e}{Colors.ENDC}")
            return []

    def execute_traffic_query_stream(self, start_time_str, end_time_str, policy_decisions):
        """
        Executes an async traffic query and yields results row by row to save memory.
        """
        payload = {
            "start_date": start_time_str, "end_date": end_time_str,
            "policy_decisions": policy_decisions,
            "max_results": MAX_TRAFFIC_RESULTS,
            "query_name": "Traffic_Monitor_Query",
            "sources": {"include": [], "exclude": []},
            "destinations": {"include": [], "exclude": []},
            "services": {"include": [], "exclude": []}
        }
        
        print(f"正在提交流量查詢 ({start_time_str} 至 {end_time_str})...")
        try:
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            r = requests.post(f"{self.base_url}/traffic_flows/async_queries", auth=self.auth, headers=headers, json=payload, verify=self.verify_ssl, timeout=10)
            
            if r.status_code not in [201, 202]: 
                print(f"API Error {r.status_code}: {r.text}")
                return

            job_url = r.json().get("href")
            print("等待流量計算中...", end="", flush=True)
            
            # Polling
            for _ in range(60): # Wait up to 2 mins
                time.sleep(2)
                status_r = requests.get(f"{self.api_cfg['url']}/api/v2{job_url}", auth=self.auth, headers=headers, verify=self.verify_ssl)
                if status_r.status_code != 200: continue
                
                state = status_r.json().get("status")
                if state == "completed":
                    print(" 完成。")
                    break
                if state == "failed":
                    print(" 失敗。")
                    return
                print(".", end="", flush=True)
            else:
                print(" Timeout.")
                return

            # Stream Download
            dl = requests.get(f"{self.api_cfg['url']}/api/v2{job_url}/download", auth=self.auth, headers=headers, verify=self.verify_ssl, stream=True)
            
            buffer = BytesIO()
            for chunk in dl.iter_content(chunk_size=8192):
                 buffer.write(chunk)
            
            buffer.seek(0)
            # Handle Gzip
            try:
                with gzip.GzipFile(fileobj=buffer, mode='rb') as f:
                    # Depending on API format, it might be a JSON array or JSON Lines.
                    # Usually Illumio Async Traffic is JSON Lines if not requested otherwise, 
                    # but the original code handled both. We'll try to read line by line.
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            # It could be a JSON array start/end if it is a single list
                            if line == b'[' or line == b']': continue
                            if line.endswith(b','): line = line[:-1]
                            data = json.loads(line)
                            if isinstance(data, list):
                                for item in data: yield item
                            else:
                                yield data
                        except: pass
            except Exception as e:
                # Fallback if not gzip
                buffer.seek(0)
                text_data = buffer.read().decode('utf-8')
                for line in text_data.splitlines():
                    if not line.strip(): continue
                    try: 
                        data = json.loads(line)
                        if isinstance(data, list):
                            for item in data: yield item
                        else:
                            yield data
                    except: pass

        except Exception as e:
            print(f"Query Exception: {e}")
            return
