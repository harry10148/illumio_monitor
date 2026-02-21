# Illumio PCE Monitor

![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square&logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen?style=flat-square)

> **[English](#english)** | **[繁體中文](#繁體中文)**

---

# English

An advanced **agentless** monitoring tool for **Illumio Core (PCE)** via REST API. Features intelligent traffic analysis, security event detection, and automated alerting — with **zero external dependencies** (Python stdlib only for CLI/daemon).

## Three Execution Modes

| Mode | Command | Description |
|:---|:---|:---|
| **Interactive CLI** | `python illumio_monitor.py` | Default, menu-driven |
| **Web GUI** | `python illumio_monitor.py --gui` | Browser-based GUI (requires Flask) |
| **Daemon Service** | `python illumio_monitor.py --monitor` | Headless background monitoring |

```bash
python illumio_monitor.py --help
python illumio_monitor.py --monitor --interval 5   # 5-minute interval (default: 10)
```

## Under the Hood: Query Architecture

The monitoring engine separates **Event** and **Traffic** queries completely, utilizing different API endpoints and tracking mechanisms to ensure maximum efficiency.

### 1. Event Monitoring (Security Events)
- **Endpoint**: `/api/v2/users/1/events`
- **Schedule**: Evaluated every 10 minutes (or customized via `--interval`).
- **Zero Duplicates**: The engine stores the precise timestamp of the last processed event in `state.json` (the `last_check` anchor). The next API query strictly filters for events occurring *after* this timestamp, guaranteeing that no event is ever alerted on twice.

### 2. Traffic & Bandwidth Monitoring
- **Endpoint**: `/api/v2/orgs/1/traffic_flows/traffic_analysis_queries`
- **Schedule**: Evaluated on the same interval loop.
- **Single-Pass Architecture**: Instead of querying the API separately for every configured rule, the engine finds the *maximum sliding window* across all your traffic/bandwidth rules (e.g., if your rules use 5m, 10m, and 30m windows, it queries exactly the last 30 minutes of traffic once).
- **Local Filtering**: Raw traffic flows are retrieved in one bulk request. The `Analyzer` then processes these flows locally in a single iteration, matching them against your configured rules (`port`, `proto`, `src_label`, `dst_label`, IP lists, and Policy Decision `pd`) and applying independent cooldowns.
- **Hybrid Calculation**: 
  - *Priority*: Interval/Delta calculation (precise traffic within the window).
  - *Fallback*: Total/Lifetime volume (for long-lived connections that haven't closed yet).

## CLI User Guide (Interactive Menu)

The default interactive CLI mode presents the following text menu. Each option provides a self-guided wizard:

```text
=== Illumio PCE Monitor ===
API: https://pce.lab.local:8443 | Rules: 7
----------------------------------------
1. Add Event Rule (inc. PCE Health Check)
2. Add Traffic Rule
3. Add Bandwidth & Volume Rule
4. Manage Rules (List/Delete)
5. System Settings (API / Email / Alerts)
6. Load Official Best Practices
7. Send Test Alert
8. Run Monitor Once
9. Traffic Rule Debug Mode
10. Launch Web GUI
0. Exit
```

### Option Details

*   **`1. Add Event Rule`**: Create alerts based on PCE audit events (e.g., `agent.tampering`, `user.login_failed`). Includes the option to enable the **PCE Health Check** monitor.
*   **`2. Add Traffic Rule`**: Create flow-based rules. You will be prompted to filter by Policy Decision (Blocked, Allowed, etc.), Port, Protocol, and optionally PCE Labels or IP Lists.
*   **`3. Add Bandwidth & Volume Rule`**: Monitor extreme data transfers. Choose between **Bandwidth** (peak rate in Mbps) or **Total Volume** (cumulative MB transferred within a window).
*   **`4. Manage Rules`**: Lists all active rules. 
    *   To **delete**, input indices separated by commas: `d 0,2,5`
    *   To **modify/edit**, input `m <index>`: `m 3` (This will launch an inplace editing wizard).
*   **`5. System Settings`**: Configure your PCE API credentials, setup SMTP for Email alerts, toggle secondary channels (LINE, Webhook), configure SSL behavior, and change the console language.
*   **`6. Load Official Best Practices`**: Quickly bootstrap the tool. This will **overwrite** your current rules and load recommended templates (e.g. Agent Offline, High Blocked Traffic).
*   **`7. Send Test Alert`**: Sends a dummy notification to all currently active alert channels to verify connectivity.
*   **`8. Run Monitor Once`**: Forces an immediate full monitoring cycle (evaluating all rules) in the console instead of waiting for the background timer.
*   **`9. Traffic Rule Debug Mode`**: A sandbox environment. Evaluates your current traffic rules against historical PCE data offline to see what *would* have triggered an alert, without actually sending one. Very useful for tuning thresholds.
*   **`10. Launch Web GUI`**: Starts the local web server and opens the browser interface for visual management.

## Web GUI

The Web GUI is a Flask-based browser application (default `http://127.0.0.1:5001`). Flask is an **optional** dependency; CLI and daemon modes work without it.

```bash
pip install flask               # Install once
python illumio_monitor.py --gui  # Opens browser automatically
```

The GUI is also accessible from CLI **Menu #10**.

### Web GUI Tabs

| Tab | Features |
|:---|:---|
| **Dashboard** | API status, active rules count, health check status, language/theme context. Test Connection & Refresh buttons. |
| **Rules** | Full CRUD: **Add** (Event / Traffic / BW-Volume), **Edit** (✏️ per row, pre-fills modal), **Delete** (checkbox + batch delete) |
| **Settings** | API connection, email/SMTP, alert channels (Mail/LINE/Webhook), language & theme toggle |
| **Actions** | Run Monitor Once, Debug Mode (configurable window & policy decision), Send Test Alert, Load Best Practices (double confirmation) |

### Web GUI REST API Endpoints

For developers who want to extend the Web GUI or build automation:

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/` | Serve the SPA HTML page |
| `GET` | `/api/status` | Dashboard data (version, API URL, rule count, theme, language) |
| `GET` | `/api/ui_translations` | Fetch active localization dictionary for GUI elements |
| `GET` | `/api/event-catalog` | Full event type catalog (grouped by category) |
| `GET` | `/api/rules` | List all rules with index |
| `GET` | `/api/rules/<index>` | Get single rule by index |
| `POST` | `/api/rules/event` | Add new event rule |
| `POST` | `/api/rules/traffic` | Add new traffic rule |
| `POST` | `/api/rules/bandwidth` | Add new bandwidth/volume rule |
| `PUT` | `/api/rules/<index>` | Update existing rule by index |
| `DELETE` | `/api/rules/<index>` | Delete rule by index |
| `GET` | `/api/settings` | Get all settings (API, email, SMTP, alerts) |
| `POST` | `/api/settings` | Save settings (partial update supported) |
| `POST` | `/api/actions/run` | Run full monitoring cycle |
| `POST` | `/api/actions/debug` | Run debug mode (body: `{mins, pd_sel}`) |
| `POST` | `/api/actions/test-alert` | Send test alert |
| `POST` | `/api/actions/best-practices` | Load best practice rules |
| `POST` | `/api/actions/test-connection` | Test PCE API connectivity |
| `POST` | `/api/shutdown` | Graceful server shutdown |

## Rule Types

### Event Rules
Monitor PCE audit events (agent tampering, login failures, API auth errors, etc.).

| Field | Description |
|:---|:---|
| `filter_value` | PCE event type (e.g. `agent.tampering`, `user.login_failed`) |
| `threshold_type` | `immediate` (alert on first occurrence) or `count` (cumulative within window) |
| `threshold_count` | Number of occurrences to trigger (for `count` type) |
| `threshold_window` | Time window in minutes |
| `cooldown_minutes` | Minimum minutes between repeated alerts |

### Traffic Rules
Monitor traffic flow counts by policy decision and filters.

| Field | Description |
|:---|:---|
| `pd` | Policy decision: `2`=Blocked, `1`=Potentially Blocked, `0`=Allowed, `-1`=All |
| `port` / `proto` | Filter by port number and protocol (`6`=TCP, `17`=UDP) |
| `src_label` / `dst_label` | Filter by PCE label (e.g. `role=Web`) |
| `src_ip_in` / `dst_ip_in` | Filter by IP or IP List name |
| `ex_*` fields | Exclude filters (same format as above) |

### Bandwidth / Volume Rules
Monitor data transfer rates (Mbps) or total transfer volume (MB).

| Field | Description |
|:---|:---|
| `type` | `bandwidth` (peak Mbps) or `volume` (total MB) |
| `threshold_count` | Threshold value in Mbps or MB |
| Same filter fields as Traffic Rules |

## Under the Hood: Parameter Guide (API 25.2)

The traffic filtering parameters (Filters / Excludes) in this tool map directly to the Illumio **Traffic Analysis REST API** specifications (refer to the official `/docs/REST_APIs_25_2.pdf` for exhaustive details):

| UI Field | API Parameter | Supported Formats & Examples |
|:---|:---|:---|
| **Port** | `port` | Must be an integer (e.g., `80`, `443`, or `3306`) |
| **Protocol** | `proto` | Converted to integer: `6` (TCP) or `17` (UDP) |
| **Source / Destination (Label)** | `label.href` | **`key=value`**: Must exactly match PCE defined keys/values (e.g., `role=Web`, `env=Production`) |
| **Source / Destination (IP)** | `ip_address` | **CIDR or Exact IP**: (e.g., `10.0.0.0/8`, `192.168.1.50`) |
| **IP List** | `ip_list.href` | Processed identically to IP filters in the API payload. |

**Policy Decisions Defined:**
*   **Blocked**: Traffic explicitly dropped by active policy.
*   **Potential**: Traffic currently allowed, but **would** be dropped if the workload transitioned to Enforced mode. (Highly useful for identifying rogue flows before enforcement).
*   **Allowed**: Traffic explicitly permitted by policy.

## Alert Channels

| Channel | Configuration |
|:---|:---|
| **Email** | SMTP host/port, authentication (optional), STARTTLS support |
| **LINE** | Channel access token + target ID (via LINE Messaging API) |
| **Webhook** | Any HTTP URL (POST with JSON payload) |

Configure active channels in `config.json` → `alerts.active` array: `["mail", "line", "webhook"]`

## Installation & Deployment

### Requirements
- Python 3.8+ (no `pip install` needed for CLI and daemon)
- Web GUI mode (`--gui`): `pip install flask`

### Quick Start
```bash
git clone <repo-url>
cd illumio_monitor
cp config.json.example config.json    # Edit with your PCE credentials
python illumio_monitor.py             # Interactive CLI
python illumio_monitor.py --gui       # Web GUI (opens browser)
```

### Configuration (`config.json`)

```jsonc
{
  "api": {
    "url": "https://pce.example.com:8443",   // PCE URL
    "org_id": "1",                           // Organization ID
    "key": "api_xxxxxxxx",                   // API Key ID
    "secret": "xxxxxxxx",                    // API Secret
    "verify_ssl": true                       // SSL certificate verification
  },
  "email": {
    "sender": "monitor@example.com",
    "recipients": ["admin@example.com"]
  },
  "smtp": {
    "host": "smtp.example.com", "port": 587,
    "user": "user", "password": "pass",
    "enable_auth": true, "enable_tls": true
  },
  "alerts": {
    "active": ["mail"],                      // Active channels
    "line_channel_access_token": "",
    "line_target_id": "",
    "webhook_url": ""
  },
  "settings": {
    "enable_health_check": true,
    "language": "en",                        // "en" or "zh_TW"
    "theme": "light"                         // "light" or "dark"
  },
  "rules": []                                // Rules added via CLI or GUI
}
```

> **Security**: `config.json` and `state.json` are excluded from Git via `.gitignore`.

### Windows Service (NSSM)

**Deployment Principle**: The Windows deployment uses a PowerShell script (`deploy/install_service.ps1`) to wrap the Python script using **NSSM (Non-Sucking Service Manager)**. It configures the Python executable to run with `--monitor` in headless mode. 

**Features enabled by NSSM**:
*   **Auto-Start**: Service is registered with `SERVICE_AUTO_START` to boot with Windows.
*   **Log Management**: Standard Output/Error are intercepted and piped into `logs/service_stdout.log` and `service_stderr.log` with an automatic 10MB file rotation.
*   **Crash Recovery**: If the Python process terminates unexpectedly, NSSM will automatically revive it after a 10-second delay.

Download [NSSM](https://nssm.cc/download), then run PowerShell **as Administrator**:

```powershell
cd deploy

# Specify NSSM path directly (no PATH setup needed):
.\install_service.ps1 -Action install -NssmPath "C:\path\to\nssm.exe"

# If NSSM is already in PATH:
.\install_service.ps1 -Action install

# Custom interval:
.\install_service.ps1 -Action install -NssmPath "C:\path\to\nssm.exe" -Interval 5

# Manage:
.\install_service.ps1 -Action status
.\install_service.ps1 -Action uninstall
```

### Linux Service (systemd)

**Deployment Principle**: The Linux deployment relies on the native `systemd` init process using the provided `deploy/illumio-monitor.service` unit file. 

**Security & Operational Features**:
*   **Least Privilege**: Runs as a dedicated restricted system user (`illumio_monitor`) with `NoNewPrivileges=true` and `ProtectSystem=strict`.
*   **Auto-Start**: Tied to `multi-user.target` for boot launch.
*   **Crash Recovery**: Configured with `Restart=always` and a `RestartSec=10` delay.
*   **Logging**: Standard output naturally flows into `journald` for native Linux log management.

```bash
sudo cp -r . /opt/illumio_monitor/
sudo useradd -r -s /bin/nologin illumio_monitor
sudo chown -R illumio_monitor:illumio_monitor /opt/illumio_monitor
sudo cp deploy/illumio-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now illumio-monitor
```

```bash
sudo systemctl status illumio-monitor    # Check status
sudo journalctl -u illumio-monitor -f    # Live logs
```

## File Structure

```
illumio_monitor/
├── illumio_monitor.py        # Entry point
├── config.json               # Configuration (API, SMTP, Rules) — gitignored
├── config.json.example       # Config template (safe for version control)
├── state.json                # Runtime state (auto-generated) — gitignored
├── requirements.txt          # Optional: flask for Web GUI
├── src/
│   ├── __init__.py           # Package init + version
│   ├── main.py               # CLI menu + argparse + daemon loop
│   ├── api_client.py         # REST API client (stdlib urllib)
│   ├── analyzer.py           # Analysis engine (event/traffic/bandwidth)
│   ├── reporter.py           # Alert dispatcher (Email / LINE / Webhook)
│   ├── config.py             # ConfigManager (load / save / CRUD rules)
│   ├── settings.py           # CLI settings menus (add rules, manage rules)
│   ├── gui.py                # Flask Web GUI (SPA + REST API endpoints)
│   ├── i18n.py               # Internationalization (en / zh_TW)
│   └── utils.py              # Utilities (logger, colors, formatting)
├── deploy/
│   ├── install_service.ps1   # Windows service (NSSM + PowerShell)
│   └── illumio-monitor.service  # Linux systemd unit
├── tests/                    # Unit tests
└── logs/                     # Log files (auto-generated)
```

## Developer Guide

### Architecture Overview

```
illumio_monitor.py ──→ src/main.py
                        ├── CLI menu mode (interactive)
                        ├── --gui → src/gui.py (Flask Web GUI)
                        └── --monitor → daemon loop
                              ├── ApiClient (src/api_client.py)  → PCE REST API
                              ├── Analyzer  (src/analyzer.py)    → Rule evaluation
                              └── Reporter  (src/reporter.py)    → Send alerts
```

### Key Classes

| Class | File | Responsibility |
|:---|:---|:---|
| `ConfigManager` | `config.py` | Load/save JSON config, add/update/delete rules, load best practices |
| `ApiClient` | `api_client.py` | HTTP requests to PCE (urllib), retry logic, SSL handling |
| `Analyzer` | `analyzer.py` | Event/traffic/bandwidth analysis, sliding window, debug mode |
| `Reporter` | `reporter.py` | Dispatch alerts via configured channels |

### Adding a New Alert Channel

1. Add channel key to `config.json` → `alerts.active` array
2. Add credentials to `config.json`
3. Implement `_send_<channel>()` method in `src/reporter.py`
4. Update `src/gui.py` Settings tab to expose the new fields

### Adding a New Rule Type

1. Define rule schema in `src/config.py` → `add_or_update_rule()`
2. Add analysis logic in `src/analyzer.py` → `run_analysis()`
3. Add CLI wizard in `src/settings.py`
4. Add Web GUI modal form and API endpoint in `src/gui.py`

### Running Tests

```bash
python -m unittest discover -s tests -v
```

## FAQ

**Q: Any packages to install?** — No for CLI/daemon. Web GUI needs `pip install flask`.

**Q: Change monitoring interval?** — `--monitor --interval 5` or `nssm edit IllumioMonitor` for Windows service.

**Q: Debug results differ from alerts?** — Different time baselines (current time vs scheduled time).

**Q: How to exclude specific subnets?** — Use the exclude filter fields in traffic rules (IP List names from PCE).

**Q: Web GUI port already in use?** — Edit `launch_gui()` in `src/gui.py` to change the default port from 5000.

---

# 繁體中文

專為 **Illumio Core (PCE)** 設計的進階**無 Agent** 監控工具。透過 REST API 實現智慧型流量分析、安全事件偵測與自動化告警。**完全使用 Python 標準函式庫**（CLI/daemon 無需外部套件）。

## 三種執行模式

| 模式 | 指令 | 說明 |
|:---|:---|:---|
| **互動式 CLI** | `python illumio_monitor.py` | 預設模式，選單操作 |
| **Web GUI** | `python illumio_monitor.py --gui` | 瀏覽器介面（需 Flask） |
| **背景服務** | `python illumio_monitor.py --monitor` | 無人值守 Daemon 模式 |

```bash
python illumio_monitor.py --help
python illumio_monitor.py --monitor --interval 5   # 5 分鐘間隔（預設 10 分鐘）
```

## 核心運作邏輯與查詢架構

監控引擎將 **Event（事件）** 與 **Traffic（流量）** 的查詢完全分離，使用不同的 API 端點與追蹤機制來確保最高效率。

### 1. 事件監控 (Security Events)
- **API 端點**: `/api/v2/users/1/events`
- **執行頻率**: 預設每 10 分鐘執行一次（可透過 `--interval` 更改）。
- **保證不重複**: 程式會將最後一次處理的事件時間戳記存入 `state.json` 中的 `last_check` 作為錨點。下一次查詢時，API 會嚴格過濾只抓取該時間點「之後」發生的最新事件，確保同一個事件絕不會被重複告警。

### 2. 流量與頻寬監控 (Traffic & Bandwidth)
- **API 端點**: `/api/v2/orgs/1/traffic_flows/traffic_analysis_queries`
- **執行頻率**: 與事件監控在同一個迴圈中執行。
- **One-Pass 單次查詢架構**: 程式不會為每一條規則單獨發送 API 請求。相反地，它會找出所有設定規則中「最長的滑動視窗」（例如：若規則分別設定為 5分鐘、10分鐘、30分鐘，程式便會一次性查詢過去 30 分鐘的所有流量）。
- **本地端過濾分析**: 取得大批的原始流量後，`Analyzer` 分析引擎會在本地端進行單次遍歷（Single Iteration），將流量與您的多個規則（包含 `port`, `proto`, Label, IP List 以及策略決定 `pd`）進行比對，並獨立計算每條規則的數值與冷卻時間。
- **混合計算模式**: 
  - *優先採用*: 區間流量 (精確計算該視窗內的傳輸量)
  - *備援機制*: 生命週期總量 (針對尚未關閉的超長連線)

## 文字介面使用指南 (CLI User Guide)

當啟動為預設文字互動模式時，若系統語言選擇繁體中文，會呈現以下選單（具備互動式引導）：

```text
=== Illumio PCE Monitor ===
API: https://pce.lab.local:8443 | Rules: 7
----------------------------------------
1. Add Event Rule (inc. PCE Health Check)
2. Add Traffic Rule
3. Add Bandwidth & Volume Rule
4. Manage Rules (List/Delete)
5. System Settings (API / Email / Alerts)
6. Load Official Best Practices
7. Send Test Alert
8. Run Monitor Once
9. Traffic Rule Debug Mode
10. Launch Web GUI
0. Exit
```

### 功能項目詳解

*   **`1. 新增事件規則`**：針對 PCE 安全稽核事件進行告警設定（例如 `agent.tampering` Agent 遭竄改、密碼錯誤等）。也可在此啟用 **PCE 節點健康度檢查 (Health Check)**。
*   **`2. 新增流量規則`**：基於網路連線（Flows）進行監控。引導精靈會請您選擇策略結果（例如：阻擋、允許）、指定 Port、通訊協定，以及進階的 Label 或 IP List 過濾。
*   **`3. 新增頻寬 / 傳輸量規則`**：監控異常的大型資料傳輸。可選擇 **頻寬 (Bandwidth)**（Mbps 即時峰值）或 **總傳輸量 (Total Volume)**（一段時間內的 MB 累積量，適合抓取資料外洩）。
*   **`4. 管理 / 刪除規則`**：列出目前生效的所有監控規則。
    *   **刪除規則**：輸入索引值的逗號分隔即可批次刪除（例：`d 0,2,5`）
    *   **修改規則**：輸入 `m <索引>` 即可進入編輯模式（例：`m 3`）
*   **`5. 系統設定`**：設定您的 PCE API 連線憑證、SMTP 寄信伺服器、開啟/關閉其他告警通道（LINE, Webhook）、設定憑證驗證（SSL Verify），以及切換中英文介面。
*   **`6. 載入官方最佳實踐預設配置`**：一鍵初始化。這會 **清空並覆寫** 您目前的設定，並載入官方推薦的監控版型（例如 Agent 離線告警、高頻率阻擋流量告警等）。
*   **`7. 發送測試告警`**：對所有啟用的告警通道（Email, LINE, Webhook 等）發送一則測試訊息，方便您驗證網路和設定是否正確。
*   **`8. 立即執行一次監控`**：強制程式立刻對所有規則執行一次 API 檢查與計算，不需等待背景計時器。
*   **`9. 流量規則模擬除錯模式`**：沙盒環境。讓您用「目前的流量規則」去跑「過去的歷史流量」，藉此觀察該規則「是否會觸發告警」，但**不會真的發送通知**。對於調教門檻值非常有用。
*  **`10. 啟動 Web GUI`**：在本地端啟動 Flask 網頁伺服器並開啟瀏覽器介面。

## 深入解析: 監控參數與 API (Parameter Guide)

本工具支援的流量過濾條件（Filters / Excludes）直接對應 Illumio **Traffic Analysis REST API** 規格 (可參閱官方文件 `/docs/REST_APIs_25_2.pdf`)：

| 介面欄位 | API 參數 | 支援的輸入格式與範例 |
|:---|:---|:---|
| **Port** | `port` | 必須是整數 (例：`80`, `443` 或 `3306`) |
| **Protocol** | `proto` | 單純設定為整數：`6` (TCP) 或 `17` (UDP) |
| **Source / Destination (Label)** | `label.href` | **`key=value`**：必須完全吻合 PCE 的 Label (例：`role=Web`, `env=Production`) |
| **Source / Destination (IP)** | `ip_address` | **CIDR 或 純 IP**：(例：`10.0.0.0/8`, `192.168.1.50`) |
| **IP List** | `ip_list.href` | 輸入名稱即等同純 IP 的解析邏輯。 |

**策略決定 (Policy Decisions) 的定義：**
*   **Blocked**: 流量確實被目前的 Policy 阻擋。
*   **Potential**: 流量目前被允許，但如果該 Workload 從 Build 進入 Enforced 模式，這些流量**將會**被阻擋。(這對於抓出預期外連線非常有幫助)
*   **Allowed**: 流量完全符合 Policy 並被放行。

## Web GUI

Web GUI 基於 Flask 的瀏覽器應用程式（預設 `http://127.0.0.1:5001`）。Flask 為**選用**套件，CLI 和 daemon 模式無需安裝。

```bash
pip install flask               # 安裝一次
python illumio_monitor.py --gui  # 自動開啟瀏覽器
```

也可從 CLI **選單 #10** 啟動。

### Web GUI 功能頁籤

| 頁籤 | 功能 |
|:---|:---|
| **Dashboard** | API 狀態、規則數量、健康檢查、語系與主題提示。測試連線與重新整理。 |
| **Rules** | 完整 CRUD：**新增** (Event / Traffic / BW-Volume)、**編輯** (✏️ 按鈕，自動帶入現有值)、**刪除** (勾選批次刪除) |
| **Settings** | API 連線、Email/SMTP、告警通道 (Mail/LINE/Webhook)、語言及明暗主題切換 |
| **Actions** | 執行監控、除錯模式、發送測試告警、載入最佳實踐 (雙重確認) |

### Web GUI REST API 端點

供開發者擴充 Web GUI 或自動化使用：

| 方法 | 端點 | 說明 |
|:---|:---|:---|
| `GET` | `/api/status` | Dashboard 資料 (包含語言及主題狀態) |
| `GET` | `/api/ui_translations` | 取得當前網頁元件所使用的翻譯字典檔 |
| `GET` | `/api/rules` | 列出所有規則 |
| `GET` | `/api/rules/<index>` | 取得單一規則 |
| `POST` | `/api/rules/event` | 新增事件規則 |
| `POST` | `/api/rules/traffic` | 新增流量規則 |
| `POST` | `/api/rules/bandwidth` | 新增頻寬/傳輸量規則 |
| `PUT` | `/api/rules/<index>` | 更新現有規則 |
| `DELETE` | `/api/rules/<index>` | 刪除規則 |
| `GET/POST` | `/api/settings` | 取得/儲存設定 |
| `POST` | `/api/actions/run` | 執行完整監控週期 |
| `POST` | `/api/actions/debug` | 除錯模式 |
| `POST` | `/api/actions/test-alert` | 發送測試告警 |
| `POST` | `/api/actions/best-practices` | 載入最佳實踐規則 |
| `POST` | `/api/actions/test-connection` | 測試 PCE 連線 |

## 規則類型

### 事件規則
監控 PCE 稽核事件（Agent 竄改、登入失敗、API 認證錯誤等）。

| 欄位 | 說明 |
|:---|:---|
| `filter_value` | PCE 事件類型 (如 `agent.tampering`) |
| `threshold_type` | `immediate` (立即) 或 `count` (累計) |
| `threshold_count` | 觸發所需次數 |
| `threshold_window` | 時間視窗 (分鐘) |
| `cooldown_minutes` | 冷卻時間 (分鐘) |

### 流量規則
依策略決定和篩選條件監控流量筆數。

| 欄位 | 說明 |
|:---|:---|
| `pd` | 策略決定：`2`=阻擋, `1`=潛在阻擋, `0`=允許, `-1`=全部 |
| `port` / `proto` | 埠號 / 協定 (`6`=TCP, `17`=UDP) |
| `src_label` / `dst_label` | PCE Label 篩選 (如 `role=Web`) |
| `ex_*` 欄位 | 排除條件 |

### 頻寬 / 傳輸量規則
監控資料傳輸速率 (Mbps) 或總傳輸量 (MB)。

## 告警通道

| 通道 | 設定 |
|:---|:---|
| **Email** | SMTP 主機/埠、認證 (選用)、STARTTLS |
| **LINE** | Channel access token + target ID |
| **Webhook** | 任意 HTTP URL (POST JSON) |

## 安裝與部署

### 系統需求
- Python 3.8+（CLI 和 daemon 無需安裝任何套件）
- Web GUI 模式 (`--gui`): `pip install flask`

### 快速開始
```bash
git clone <repo-url>
cd illumio_monitor
cp config.json.example config.json    # 編輯填入 PCE 連線資訊
python illumio_monitor.py             # 互動式 CLI
python illumio_monitor.py --gui       # Web GUI（開啟瀏覽器）
```

### Windows 服務 (NSSM)

**部署原理**：Windows 部署採用 PowerShell 腳本 (`deploy/install_service.ps1`)，結合第三方工具 **NSSM (Non-Sucking Service Manager)** 將 Python 腳本封裝為原生系統服務。此腳本將強制 Python 以無介面（Headless）及 `--monitor` 背景模式執行。

**NSSM 帶來的效益**：
*   **開機自啟**：服務被註冊為自動啟動 (`SERVICE_AUTO_START`)，確保開機後常駐監控。
*   **日誌管理**：標準輸出與錯誤 (Stdout/Stderr) 會被 NSSM 攔截，導入 `logs/service_stdout.log` 中，並具備自動日誌輪替功能（滿 10MB 自動切割）。
*   **崩潰復原**：若 Python 程序發生異常崩潰，NSSM 會在 10 秒後自動將其重新啟動。

下載 [NSSM](https://nssm.cc/download)，以**管理員權限**執行 PowerShell：

```powershell
cd deploy

# 直接指定 NSSM 路徑（不需設定 PATH）：
.\install_service.ps1 -Action install -NssmPath "C:\path\to\nssm.exe"

# 如果 NSSM 已加入 PATH：
.\install_service.ps1 -Action install

# 自訂間隔：
.\install_service.ps1 -Action install -NssmPath "C:\path\to\nssm.exe" -Interval 5

# 管理：
.\install_service.ps1 -Action status
.\install_service.ps1 -Action uninstall
```

### Linux 服務 (systemd)

**部署原理**：Linux 部署直接依賴原生的系統管理工具 `systemd`，透過隨附的 `deploy/illumio-monitor.service` 配置檔將程式註冊為 Daemon 守護進程。

**安全性與運作特性**：
*   **最小權限原則**：服務指定以新建的受限系統帳號 (`illumio_monitor`) 執行，禁止登入且不具備 sudo 權限。並啟用 `NoNewPrivileges=true` 與 `ProtectSystem=strict` 防止系統檔案遭竄改。
*   **開機啟動與復原**：隨 `multi-user.target` 開機啟動，並設定 `Restart=always` 搭配 10 秒延遲，確保服務中斷後自我修復。
*   **原生整合日誌**：捨棄傳統文字檔寫入，其輸出的 Log 自動無縫對接 Linux 的 `journald` 日誌系統。

```bash
sudo cp -r . /opt/illumio_monitor/
sudo useradd -r -s /bin/nologin illumio_monitor
sudo chown -R illumio_monitor:illumio_monitor /opt/illumio_monitor
sudo cp deploy/illumio-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now illumio-monitor
```

```bash
sudo systemctl status illumio-monitor    # 查看狀態
sudo journalctl -u illumio-monitor -f    # 即時日誌
```

## 檔案結構

```
illumio_monitor/
├── illumio_monitor.py        # 主程式進入點
├── config.json               # 設定檔 (API, SMTP, Rules) — 已排除 Git
├── config.json.example       # 設定檔範本 (可安全提交)
├── state.json                # 運行時狀態 (自動產生) — 已排除 Git
├── requirements.txt          # 選用：flask (Web GUI)
├── src/
│   ├── __init__.py           # 套件初始化 + 版本號
│   ├── main.py               # CLI 選單 + argparse + daemon 迴圈
│   ├── api_client.py         # REST API 客戶端 (stdlib urllib)
│   ├── analyzer.py           # 分析引擎 (事件/流量/頻寬)
│   ├── reporter.py           # 告警發送 (Email / LINE / Webhook)
│   ├── config.py             # ConfigManager (載入/儲存/規則 CRUD)
│   ├── settings.py           # CLI 設定選單 (新增/管理規則)
│   ├── gui.py                # Flask Web GUI (SPA + REST API 端點)
│   ├── i18n.py               # 多語系 (en / zh_TW)
│   └── utils.py              # 工具函式 (logger, colors, formatting)
├── deploy/
│   ├── install_service.ps1   # Windows 服務 (NSSM + PowerShell)
│   └── illumio-monitor.service  # Linux systemd 單元
├── tests/                    # 單元測試
└── logs/                     # 日誌 (自動產生)
```

## 開發者指南

### 架構概覽

```
illumio_monitor.py ──→ src/main.py
                        ├── CLI 選單模式 (互動式)
                        ├── --gui → src/gui.py (Flask Web GUI)
                        └── --monitor → daemon 迴圈
                              ├── ApiClient  → PCE REST API
                              ├── Analyzer   → 規則評估
                              └── Reporter   → 發送告警
```

### 關鍵類別

| 類別 | 檔案 | 職責 |
|:---|:---|:---|
| `ConfigManager` | `config.py` | 載入/儲存 JSON 設定、新增/更新/刪除規則、載入最佳實踐 |
| `ApiClient` | `api_client.py` | HTTP 請求 (urllib)、重試邏輯、SSL 處理 |
| `Analyzer` | `analyzer.py` | 事件/流量/頻寬分析、滑動視窗、除錯模式 |
| `Reporter` | `reporter.py` | 透過設定的通道派送告警 |

### 新增告警通道

1. 在 `config.json` → `alerts.active` 陣列新增通道名稱
2. 在 `config.json` 新增對應的憑證欄位
3. 在 `src/reporter.py` 實作 `_send_<channel>()` 方法
4. 在 `src/gui.py` Settings 頁籤新增設定項目

### 新增規則類型

1. 在 `src/config.py` → `add_or_update_rule()` 定義規則結構
2. 在 `src/analyzer.py` → `run_analysis()` 新增分析邏輯
3. 在 `src/settings.py` 新增 CLI 互動精靈
4. 在 `src/gui.py` 新增 Web GUI 表單和 API 端點

### 執行測試

```bash
python -m unittest discover -s tests -v
```

## 常見問題

**Q: 需要安裝套件嗎？** — CLI/daemon 不需要。Web GUI 需 `pip install flask`。

**Q: 如何更改監控間隔？** — `--monitor --interval 5` 或 Windows 服務用 `nssm edit IllumioMonitor`。

**Q: Debug 結果跟告警不同？** — 基準時間不同（當下時間 vs 排程觸發時間）。

**Q: 如何排除特定網段？** — 在規則的排除條件欄位輸入 PCE 上的 IP List 名稱。

**Q: Web GUI 埠號被佔用？** — 編輯 `src/gui.py` 中 `launch_gui()` 的 port 參數（預設 5000）。
