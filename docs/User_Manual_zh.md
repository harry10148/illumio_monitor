# Illumio PCE Monitor - 完整使用手冊

> **[English](User_Manual.md)** | **[繁體中文](User_Manual_zh.md)**

本手冊提供 **Illumio PCE Monitor** 的完整操作指南、運作原理與設定範例。這是一個專為 Illumio Core (PCE) 設計的進階無 Agent（Agentless）監控工具，透過 REST API 提供自動化的安全事件與流量告警。

---

## 1. 架構與運作原理

監控引擎採取「事件」與「流量」雙軌並行的查詢架構，不僅提升檢查效率，更減少對 PCE 的 API 負擔。預設每 **10 分鐘**背景自動喚醒一次執行檢查。

### 1.1 事件監控 (Security Events)
針對 Illumio PCE 本身的稽核與維運事件進行監控。
- **防止重複告警**：系統會在本地 `state.json` 記錄上一次檢查的「最後時間戳記 (last_check)」。每次呼叫 API 時，只會嚴格拉取發生在這個時間戳記「之後」的事件。
- **支援次數累計**：可設定在指定視窗內發生 N 次才觸發告警（例如：10 分鐘內密碼錯誤 5 次），或選擇立即觸發。

### 1.2 流量與頻寬監控 (Traffic & Bandwidth)
針對 Workload 之間的網路連線 (Traffic Flows) 與資料傳輸量進行分析。
- **單次最大查詢 (One-Pass Architecture)**：為避免對 PCE 發起大量重複查詢，系統會在本地掃描您設定的所有流量規則，找出「最長的監控視窗」（例如您有 5分鐘 和 30分鐘 的規則，系統就只對 API 查詢過去 30 分鐘的資料一次）。
- **本地高效過濾**：取得大量歷史流量後，分析引擎 (`Analyzer`) 會在本地記憶體中一次遍歷所有資料，將每一筆連線與您的各項規則條件（Port, Protocol, Label, IP 等）進行交叉比對。
- **混合計算模式**：計算頻寬與傳輸量時，優先採用精確的「區間計算 (Delta)」，針對無法取得精確落差的長連線，則採用「生命週期總量 (Lifetime volume)」作為備援，確保異常大流量不漏抓。

---

## 2. 執行模式介紹

系統支援三種截然不同的執行模式，滿足操作與背景服務需求：

| 模式 | 指令範例 | 適用場景 |
|:---|:---|:---|
| **文字互動選單 (CLI)** | `python illumio_monitor.py` | 初次設定、手動管理規則、快速測試連線。 |
| **網頁圖形介面 (Web GUI)** | `python illumio_monitor.py --gui` | 提供視覺化的儀表板與更直覺的操作體驗（需安裝 Flask）。預設於 `http://127.0.0.1:5001` 開啟。 |
| **背景守護進程 (Daemon)** | `python illumio_monitor.py --monitor` | 部署於伺服器 24/7 不間斷執行。可透過 `--interval 5` 自訂檢查頻率（單位：分鐘）。 |

---

## 3. 文字介面 (CLI) 操作說明與範例

執行 `python illumio_monitor.py` 後，將出現互動式主選單：

```text
=== Illumio PCE Monitor ===
API: https://pce.lab.local:8443 | Rules: 2
----------------------------------------
1. Add Event Rule (inc. PCE Health Check)
2. Add Traffic Rule
...
0. Exit
```

### 範例：新增一筆安全事件告警
1. 選擇 `1` (Add Event Rule)。
2. 系統提示輸入 Event Type。例如輸入：`agent.tampering`（Agent 遭竄改）。
3. 選擇 threshold（觸發門檻），輸入 `1` 代表發生一次就告警。
4. 選擇 Window（視窗），輸入 `10` 代表檢查過去 10 分鐘。
5. 完成後，每當有 Workload 的 Agent 送出竄改事件，系統便會發送告警。

### 範例：檢查與刪除規則
1. 選擇 `4` (Manage Rules)。系統將列出目前清單與對應的數字索引 (Index)。
2. 依照提示，若要刪除索引 0 和 2 的規則，輸入 `d 0,2`。

---

## 4. 網頁介面 (Web GUI) 操作說明

執行 `python illumio_monitor.py --gui` 後，瀏覽器將自動開啟管理介面。

**小提示**：預設已為您套用 **明亮主題 (Light Theme)** 與 **英文介面**。您可隨時在「Settings (系統設定)」頁籤將語言切換為「繁體中文」，介面不需要重新整理就會即時切換。

- **Dashboard (主控台)**：查看整體 API 狀態、執行次數、與健康狀態。內建 [Run Monitor Once] 按鈕可立即觸發檢查。
- **Rules (監控規則)**：以表格方式列出所有的事件、流量與傳輸量規則。
  - 勾選左方 Checkbox 可以點擊右上角紅色按鈕批量刪除。
  - 點擊列表最右方的 **紫色鉛筆圖示** 會展開編輯視窗，並預先載入原先的設定值方便快速修改。
- **Actions (執行動作)**：可以一鍵「載入最佳實踐 (Best Practices)」，這會自動建立基礎防禦的規則（包含 Agent 離線、防竄改、登入失敗等）。

---

## 5. 規則類型與過濾器詳解

本系統的過濾機制與 Illumio Traffic Analysis API 達到 100% 對應。

### 5.1 事件規則 (Event Rules)
監聽特定的 PCE 事件，如登入錯誤 (`user.login_failed`)。
- **門檻模式**：支援 `immediate`（有發生就告警）與 `count`（一段時間內發生滿 N 次才告警）。

### 5.2 流量規則 (Traffic Rules)
用於偵測連線數量的暴衝。
- **Policy Decision (pd)**：
  - `Blocked (2)`: 實際被阻擋的連線。
  - `Potential (1)`: 若目前 Build 狀態的機器轉為 Enforced 時，將會被阻擋的連線（預測預警非常有幫助）。
  - `Allowed (0)`: 放行的連線。
- **過濾條件**：
  - **Port / Proto**：限定協定，如 Port `443` 或 Proto `6` (TCP)。
  - **Label**：必須完全吻合 PCE 的機碼組合，例：`role=Web`。
  - **IP / IP List**：輸入如 `10.0.0.0/8` 的 CIDR，或是輸入 Illumio IP List 物件的名稱。
  - 支援 **排除 (Exclude)** 上述任何條件。

### 5.3 頻寬與傳輸量規則 (Bandwidth & Volume Rules)
專攻資料外洩 (Data Exfiltration) 預警。
- **Bandwidth**：計算峰值速率，單位為 Mbps。
- **Volume**：計算一段時間內的總傳輸資料量，單位為 MB。

---

## 6. 系統設定與告警通道

所有設定檔皆明碼儲存於 `config.json` 中，可透過純文字編輯器修改，或透過 CLI/GUI 介面操作。本檔案**不會**被上傳或備份至 Git 倉庫中以保證安全。

支援三種告警通道，可同時觸發：
1. **Email 電子郵件**：支援 SMTP、STARTTLS 以及 SSL/TLS 加密認證。
2. **LINE Notify / Messaging API**：需填入您的 Channel Access Token 與發送的 Target ID。
3. **Webhook 串接**：可用於發送標準的 JSON Payload 給自建伺服器、Slack 或 Microsoft Teams 等。

**啟用通道**：在系統設定中，勾選對應的通道（或於 `config.json` 的 `alerts.active` 陣列中保留該字串如 `["mail", "line"]`）即可啟用。
