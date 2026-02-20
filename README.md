# Illumio PCE Monitor (v1.0.0)

![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.6%2B-yellow?style=flat-square&logo=python&logoColor=white)

這是一個專為 **Illumio Core (PCE)** 設計的進階監控工具。它透過 REST API 實現 **無 Agent (Agentless)** 監控，具備智慧型流量分析、安全事件偵測與自動化告警功能。

本工具採用 **單次遍歷 (One-Pass Processing)** 演算法，極大化 API 查詢效率，並支援 **混合計算模式 (Hybrid Calculation)** 以精準呈現瞬時頻寬與長連線累積流量。

---

## 📖 目錄

- [核心運作邏輯 (Core Logic)](#-核心運作邏輯-core-logic)
- [功能選單詳解 (Menu Guide)](#-功能選單詳解-menu-guide)
- [告警報表說明 (Report Analysis)](#-告警報表說明-report-analysis)
- [安裝與自動化 (Installation)](#-安裝與自動化-installation)
- [常見問題 (FAQ)](#-常見問題-faq)

---

## 🧠 核心運作邏輯 (Core Logic)

本工具的設計核心在於「精準度」與「效能」的平衡。

### 1. 事件監控 (Event Monitoring) - 增量指標
* **原理**: 使用「最後檢查時間點 (`last_check`)」作為錨點。
* **流程**:
    1.  讀取 `illumio_pce_state.json` 取得上次執行時間。
    2.  API 僅查詢 `timestamp >= last_check` 的新事件。
    3.  執行後更新 `last_check` 為當下時間。
* **優勢**: 確保**零遺漏**且**不重複**告警。

### 2. 流量/頻寬監控 - 動態滑動視窗 (Dynamic Sliding Window)
* **原理**: 採用 **One-Pass (單次遍歷)** 技術，避免對 PCE 進行多次重複查詢。
* **流程**:
    1.  **動態查詢**: 程式會掃描所有啟用的規則，找出「最大」所需的時間窗口 (例如：規則 A 需 10 分鐘，規則 B 需 60 分鐘，則 API 查詢 60 分鐘)。
    2.  **記憶體過濾**: 資料拉回後，程式會在記憶體中針對每條規則進行時間切割。
        * *範例*: 針對規則 A (10m)，程式會自動剔除 11~60 分鐘前的舊資料，只計算最近 10 分鐘的數據。
    3.  **Top 10 採樣**: 針對觸發閾值的規則，自動保留前 10 筆最耗資源的連線樣本。

### 3. 混合計算模式 (Hybrid Calculation)
針對 Illumio 流量日誌特性，本工具會自動判斷使用哪種數值：
* **優先使用 (Interval/Delta)**: 計算該次時間窗口內實際產生的流量 (精準頻寬)。
* **備援使用 (Total/Lifetime)**: 若 API 回傳的區間流量為 0 (常見於長連線或非同步寫入)，則讀取該連線的「生命週期總傳輸量」，避免漏報重大流量。

### 4. 冷卻機制 (Cooldown)
* 每條規則擁有獨立的 State。若觸發告警，該規則會進入冷卻期 (例如 30 分鐘)。
* 冷卻期間內即使數值再次超標，也不會發送 Email，防止信箱被轟炸。

---

## 🖥️ 功能選單詳解 (Menu Guide)

### `1. 新增事件規則 (含 PCE Health Check)`
* **PCE Health Check**: 每次執行時優先檢查 `/api/v2/health`，若 Cluster 異常直接發送紅色告警。
* **Event Rule**: 監控 Audit Logs。
    * **Immediate (立即)**: 適用於高風險事件 (如 Agent 遭到竄改、被停用)。
    * **Count (累積)**: 適用於頻率偵測 (如 10 分鐘內登入失敗超過 5 次)。

### `2. 新增流量規則 (Traffic Rule)`
* 監控被防火牆 Policy 阻擋的行為。
* **Policy Decision**:
    * `Blocked`: 確定被阻擋的流量。
    * `Potentially Blocked`: 潛在阻擋 (通常發生在 Test 模式)。
* **過濾器**: 支援 Port, Protocol, Source/Destination (Label/IP/IPList)。

### `3. 新增頻寬與傳輸量規則 (Bandwidth & Volume)`
* **Bandwidth (頻寬)**: 單位 `Mbps`。監控連線的傳輸速率。觸發條件為 **Max** (任一連線超過即告警)。
* **Volume (傳輸量)**: 單位 `MB`。監控資料傳輸總量。觸發條件為 **Sum** (窗口內總量超過即告警)。
* **💡 設定技巧**:
    * **IP List**: 在來源/目的欄位直接輸入 IP List 名稱 (例如 `Corporate_VPN`)，**無需**加任何前綴。

### `4. 管理規則`
* 查看目前運作中的所有規則 ID、閾值與參數。支援刪除功能。

### `5. 系統設定`
* 設定 API URL, Key, Secret 以及 SMTP 郵件伺服器資訊。

### `6. 載入官方最佳實踐`
* **注意**: 此操作會覆蓋現有規則。
* 自動載入推薦規則：Agent Tampering, Agent Offline, Provisioning, High Traffic Blocked 等。

### `8. 立即執行監控 (Run Once)`
* **這是 Crontab 實際執行的模式**。
* 執行完整流程：Health Check -> Fetch -> Analyze -> Alert -> Update State。

### `9. 流量規則模擬與除錯 (Debug Mode)`
* **沙盒模式**：不會發信，不會更新 State 檔。
* 允許指定回溯時間 (例如查詢過去 60 分鐘)。
* 顯示每一條規則的匹配筆數、計算結果與判定狀態 (PASS / WOULD TRIGGER)。

---

## 📊 告警報表說明 (Report Analysis)

Email 告警表格經過優化，欄位定義如下：

| 欄位 | 說明 |
| :--- | :--- |
| **Value** | 該連線的監測數值。<br>• `(Interval)`: 精準區間流量。<br>• `(Avg/Total)`: 長連線的平均或總量 (當區間流量無法取得時)。 |
| **First Seen** | 該連線在 Illumio 記錄中 **首次出現** 的時間。 |
| **Last Seen** | 該連線在 Illumio 記錄中 **最後一次活躍** 的時間。<br>⚠️ *若 First 與 Last 相距甚遠 (如 10 小時)，代表這是長連線，Total Volume 通常會很大。* |
| **Dir** | 流量方向 (IN / OUT)。 |
| **Source / Dest** | 來源與目的。顯示 Workload Name, IP 以及相關 Labels。 |
| **Decision** | 防火牆決策 (Blocked / Potential / Allowed)。 |

---

## 🚀 安裝與自動化 (Installation)

## 🚀 安裝與自動化 (Installation)

### 1. 系統需求 (System Requirements)
* Python 3.6+
* Python Requests 模組 (`pip3 install requests`)

#### Windows
1. 下載並安裝 [Python 3](https://www.python.org/downloads/windows/) (安裝時請勾選 **Add Python to PATH**)。
2. 開啟 PowerShell 或 CMD 安裝相依套件：
   ```powershell
   pip install requests
   ```

#### Linux / macOS
**RHEL / Rocky / CentOS:**
```bash
sudo dnf install python3 python3-requests -y
```

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install python3 python3-requests -y
```

### 2. 執行與排程 (Execution & Scheduling)

#### Windows
* **互動模式 (Interactive)**:
    雙擊專案目錄下的 `run_monitor.bat` 即可啟動選單。

* **自動化排程 (Task Scheduler)**:
    本專案提供 `scheduled_run.bat` 用於自動化執行 (對應 Run Once 模式)。
    1. 開啟 **工作排程器 (Task Scheduler)**。
    2. 建立基本工作，名稱設為 "Illumio Monitor"。
    3. 觸發程序: 選擇「每天」，並在進階設定中勾選「每隔 5 或 10 分鐘重複工作」。
    4. 動作: 選擇 **啟動程式**。
        * **程式/指令碼**: 瀏覽並選擇 `scheduled_run.bat`。
        * **開始位置 (Start in)**: 填入專案目錄路徑 (重要!)。

#### Linux (Crontab)
建議每 5 或 10 分鐘執行一次。

```bash
# 每 10 分鐘執行一次監控 (輸入 8 代表 Run Once 模式)
*/10 * * * * cd /path/to/monitor_dir && echo "8" | python3 monitor_wrapper.py >> /path/to/monitor_dir/logs/illumio_monitor.log 2>&1
```

---

## ❓ 常見問題 (FAQ)

**Q: 為什麼 Debug Mode 看到的流量跟 Email 告警的不一樣？**

Debug Mode 是以「當下時間」往前推算；Crontab 是以「排程觸發時間」往前推算。基準點不同，數據自然會有差異。

**Q: 為什麼有些連線的 Value 顯示 (Total) 且數值很大？**

這是 Illumio 對於長連線 (Long-lived connection) 的特性。當 API 在短時間內沒有結算區間流量時，程式會自動讀取該連線的「累計總量」作為備援，以防止漏掉發生在監控空窗期的大流量。請參考 First Seen 與 Last Seen 來判斷連線持續時間。

**Q: 如何排除特定網段的流量？**

在新增規則時，於「排除條件 (Excludes)」的 Source/Destination 欄位中，直接輸入 PCE 上的 IP List 名稱 (例如 Scanner_Network) 即可。
