# Illumio PCE Monitor (v1.0.0)

![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square&logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen?style=flat-square)

> **[English](#english)** | **[繁體中文](#繁體中文)**

---

# English

An advanced **agentless** monitoring tool for **Illumio Core (PCE)** via REST API. Features intelligent traffic analysis, security event detection, and automated alerting — with **zero external dependencies** (Python stdlib only).

## Three Execution Modes

| Mode | Command | Description |
|:---|:---|:---|
| **Interactive CLI** | `python illumio_monitor.py` | Default, menu-driven |
| **Desktop GUI** | `python illumio_monitor.py --gui` | Tkinter GUI (also from CLI menu #10) |
| **Daemon Service** | `python illumio_monitor.py --monitor` | Headless background monitoring |

```bash
python illumio_monitor.py --help
python illumio_monitor.py --monitor --interval 5   # 5-minute interval (default: 10)
```

## Core Logic

| Feature | Description |
|:---|:---|
| **Event Monitoring** | Incremental queries via `last_check` anchor in `state.json` → zero duplicates |
| **Traffic/Bandwidth** | One-Pass processing with dynamic sliding window; single API query for all rules |
| **Hybrid Calculation** | Priority: Interval/Delta (precise) → Fallback: Total/Lifetime (long-lived connections) |
| **Cooldown** | Per-rule independent cooldown prevents alert flooding |
| **Retry Logic** | Exponential backoff for HTTP 429 (rate limit) and 5xx errors, up to 3 retries |

## Menu Guide

| # | Function | # | Function |
|:--|:---|:--|:---|
| 1 | Add Event Rule (+ Health Check) | 6 | Load Best Practices |
| 2 | Add Traffic Rule | 7 | Send Test Alert |
| 3 | Add Bandwidth & Volume Rule | 8 | Run Once (full cycle) |
| 4 | Manage Rules | 9 | Debug Mode (sandbox) |
| 5 | System Settings | 10 | Launch GUI |

## Installation & Deployment

### Requirements
- Python 3.8+ (no `pip install` needed)
- Linux GUI support (if using `--gui`):
  - Ubuntu/Debian: `sudo apt install python3-tk`
  - RHEL/Rocky: `sudo dnf install python3-tkinter`

### Quick Start
```bash
python illumio_monitor.py          # Interactive CLI
python illumio_monitor.py --gui    # Desktop GUI
```

### Windows Service (NSSM)

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

**Features**: Auto-start (`SERVICE_AUTO_START`), crash recovery (restart after 10s), log rotation (10MB).

### Linux Service (systemd)

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

**Features**: Auto-start (`multi-user.target`), crash recovery (`Restart=always`, 10s delay), security hardening (`NoNewPrivileges`, `ProtectSystem=strict`).

## File Structure

```
illumio_monitor/
├── illumio_monitor.py        # Entry point
├── config.json               # Configuration (API, SMTP, Rules)
├── config.json.example       # Template
├── state.json                # Runtime state (auto-generated)
├── src/
│   ├── main.py               # CLI + argparse + Daemon loop
│   ├── api_client.py         # REST API client (urllib)
│   ├── analyzer.py           # Analysis engine
│   ├── reporter.py           # Email / LINE / Webhook alerting
│   ├── config.py             # Config management
│   ├── settings.py           # CLI settings menu
│   ├── gui.py                # Tkinter GUI
│   ├── i18n.py               # i18n (en / zh_TW)
│   └── utils.py              # Utilities
├── deploy/
│   ├── install_service.ps1   # Windows service (NSSM + PowerShell)
│   └── illumio-monitor.service  # Linux systemd unit
├── tests/                    # Unit tests
└── logs/                     # Logs (auto-generated)
```

## FAQ

**Q: Any packages to install?** — No. Pure Python stdlib.

**Q: Change monitoring interval?** — `--monitor --interval 5` or `nssm edit IllumioMonitor` for Windows service.

**Q: Debug results differ from alerts?** — Different time baselines (current time vs scheduled time).

---

# 繁體中文

專為 **Illumio Core (PCE)** 設計的進階**無 Agent** 監控工具。透過 REST API 實現智慧型流量分析、安全事件偵測與自動化告警。**完全使用 Python 標準函式庫**，無需外部套件。

## 三種執行模式

| 模式 | 指令 | 說明 |
|:---|:---|:---|
| **互動式 CLI** | `python illumio_monitor.py` | 預設模式，選單操作 |
| **桌面 GUI** | `python illumio_monitor.py --gui` | Tkinter 圖形介面（亦可從選單 #10 啟動） |
| **背景服務** | `python illumio_monitor.py --monitor` | 無人值守 Daemon 模式 |

```bash
python illumio_monitor.py --help
python illumio_monitor.py --monitor --interval 5   # 5 分鐘間隔（預設 10 分鐘）
```

## 核心運作邏輯

| 功能 | 說明 |
|:---|:---|
| **事件監控** | 以 `state.json` 中的 `last_check` 為錨點增量查詢 → 零遺漏、不重複 |
| **流量/頻寬** | One-Pass 單次遍歷 + 動態滑動視窗，所有規則共用單次 API 查詢 |
| **混合計算** | 優先：區間流量 (精準) → 備援：生命週期總量 (長連線) |
| **冷卻機制** | 每條規則獨立冷卻期，防止重複告警 |
| **重試邏輯** | HTTP 429 及 5xx 自動指數退避重試，最多 3 次 |

## 功能選單

| # | 功能 | # | 功能 |
|:--|:---|:--|:---|
| 1 | 新增事件規則 (含 Health Check) | 6 | 載入最佳實踐 |
| 2 | 新增流量規則 | 7 | 發送測試告警 |
| 3 | 新增頻寬/傳輸量規則 | 8 | 立即執行監控 |
| 4 | 管理規則 | 9 | 模擬除錯 (沙盒) |
| 5 | 系統設定 | 10 | 啟動 GUI |

## 安裝與部署

### 系統需求
- Python 3.8+（無需 `pip install` 任何套件）
- Linux GUI 支援（若使用 `--gui`）：
  - Ubuntu/Debian: `sudo apt install python3-tk`
  - RHEL/Rocky: `sudo dnf install python3-tkinter`

### 快速開始
```bash
python illumio_monitor.py          # 互動式 CLI
python illumio_monitor.py --gui    # 桌面 GUI
```

### Windows 服務 (NSSM)

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

**特性**：自動啟動、崩潰後 10 秒自動重啟、日誌 10MB 自動輪替。

### Linux 服務 (systemd)

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

**特性**：開機自動啟動、崩潰自動重啟 (`Restart=always`)、安全強化 (`NoNewPrivileges`)。

## 檔案結構

```
illumio_monitor/
├── illumio_monitor.py        # 主程式進入點
├── config.json               # 設定檔 (API, SMTP, Rules)
├── config.json.example       # 設定檔範本
├── state.json                # 運行時狀態 (自動產生)
├── src/
│   ├── main.py               # CLI + argparse + Daemon 迴圈
│   ├── api_client.py         # REST API 客戶端 (urllib)
│   ├── analyzer.py           # 分析引擎
│   ├── reporter.py           # Email / LINE / Webhook 告警
│   ├── config.py             # 設定檔管理
│   ├── settings.py           # CLI 設定選單
│   ├── gui.py                # Tkinter 桌面 GUI
│   ├── i18n.py               # 多語系 (en / zh_TW)
│   └── utils.py              # 工具函式
├── deploy/
│   ├── install_service.ps1   # Windows 服務 (NSSM + PowerShell)
│   └── illumio-monitor.service  # Linux systemd 單元
├── tests/                    # 單元測試
└── logs/                     # 日誌 (自動產生)
```

## 常見問題

**Q: 需要安裝套件嗎？** — 不需要，完全使用 Python 標準函式庫。

**Q: 如何更改監控間隔？** — `--monitor --interval 5` 或 Windows 服務用 `nssm edit IllumioMonitor`。

**Q: Debug 結果跟告警不同？** — 基準時間不同（當下時間 vs 排程觸發時間）。

**Q: 如何排除特定網段？** — 在規則的排除條件欄位輸入 PCE 上的 IP List 名稱。
