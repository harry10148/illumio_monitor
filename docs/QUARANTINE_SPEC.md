# Illumio PCE 隔離功能 (Quarantine Feature) 開發規格書

## 1. 專案概述 (Overview)
本文件定義了「流量分析與即時隔離 (Traffic Analysis & Quarantine)」功能的獨立開發規格。此功能旨在提供維運與資安人員一個互動式面板，不僅能基於多重條件 (如特定 Port、IP、Policy Decision) 查詢目前的網路流量 (Traffic Flows)，並能針對異常的流量來源或目標工作負載 (Workload) 直接透過介面套用「隔離標籤 (Quarantine Labels)」。

本功能將與 Illumio PCE 深度整合，透過 REST API 進行標籤管理、工作負載狀態更新及流量數據處理。

---

## 2. 核心使用場景 (Use Cases)
1. **威脅獵捕與流量查詢**：使用者可以在面板設定時間區間、Policy Decision (Blocked, Allowed, Potential) 以及過濾條件 (例如：排除特定網段或只看特定 Port)，系統會列出連線數、頻寬 (Bandwidth) 或傳輸量 (Volume) 的 Top 10 名單。
2. **標籤初始化**：系統背景自動確認 PCE 中是否已經存在鍵值 (Key) 為 `Quarantine`，數值 (Value) 為 `Mild`, `Moderate`, `Severe` 的三個標籤，若無則自動建立。
3. **一鍵隔離 (One-Click Quarantine)**：針對列表中的異常連線，使用者可點擊「隔離」按鈕並選擇嚴重程度 (Mild/Moderate/Severe)，系統將自動找出該 Workload，並將對應的標籤附加其上，從而觸發預設的 PCE Policy 實行網路隔離。

---

## 3. 架構與 Illumio REST API 參考
本功能的所有互動皆需符合 Illumio REST API 規範 (參考基準：REST APIs 25.2.x)。

### 3.1 標籤管理 (Label API)
為了確保隔離標籤存在，系統需在初始化階段或處理隔離請求前確認標籤的 `href`。
* **查詢標籤**:
  * **Endpoint**: `GET /api/v2/orgs/:org_id/labels?key=Quarantine`
  * **邏輯**: 檢查回傳的 JSON 陣列中是否包含 `value` 為 `Mild`, `Moderate`, `Severe` 的物件。若存在，記錄其 `href` 保留備用。
* **建立標籤** (若不存在時):
  * **Endpoint**: `POST /api/v2/orgs/:org_id/labels`
  * **Payload**: `{"key": "Quarantine", "value": "Mild"}` (或 Moderate/Severe)
  * **處理**: 成功建立 (HTTP 201) 後，解析回傳 JSON 取得新標籤的 `href`。

### 3.2 流量分析 (Traffic Queries API)
這是獲取目前網路連線的核心 API。
* **非同步流量查詢**:
  * **Endpoint**: `POST /api/v2/orgs/:org_id/traffic_flows/async_queries`
  * **Payload 範例**:
    ```json
    {
      "start_date": "2026-02-23T00:00:00Z",
      "end_date": "2026-02-23T23:59:59Z",
      "policy_decisions": ["blocked", "potentially_blocked", "allowed"],
      "max_results": 100000
    }
    ```
  * **處理流程**: 
    1. 提交上述 POST 請求後，會收到 HTTP 202 及 `href` (如 `/api/v2/orgs/1/traffic_flows/async_queries/1234`)。
    2. 定期 Poll 該 `href` 直到 `status` 變為 `completed`。
    3. 呼叫 `GET /api/v2/orgs/1/traffic_flows/async_queries/1234/download` 取得 GZIP 壓縮的流量結果。

### 3.3 工作負載更新 (Workload API)
當點擊「隔離」按鈕時，前端必須傳遞目標的 Workload `href` 及選擇的隔離等級。
* **獲取 Workload 狀態**:
  * **Endpoint**: `GET /api/v2/orgs/:org_id/workloads/:workload_id` (Note: 前端列表拿到的通常就是完整的 `/orgs/1/workloads/xxxx` 路徑)
  * **邏輯**: 讀取目前的 `labels` 陣列。
* **更新 Workload 標籤**:
  * **Endpoint**: `PUT /api/v2/orgs/:org_id/workloads/:workload_id`
  * **更新邏輯**: 
    1. 複製前一步驟拿到的 `labels` 陣列。
    2. 過濾掉任何 `key` 等於 `Quarantine` 的既有標籤 (避免重複貼標)。
    3. 加入新的隔離標籤 `href` (例如：`{"href": "/orgs/1/labels/5678"}`)。
    4. 發送 PUT 請求包含更新後的 `{"labels": [...] }`。

---

## 4. 流量計算與分析邏輯 (Traffic Calculation)
非同步流量 API 下載回來的 JSON 紀錄需要經過清洗與聚合計算法能呈現在 GUI 上，計算邏輯應參考現行 Traffic Alert 的實作方式。

每一筆流量紀錄 (Flow Record) 均包含收發雙方的位元組 (Bytes)、時間區間、連線數等屬性。我們需要針對 **頻寬 (Bandwidth)** 與 **傳輸量 (Volume)** 進行聚合計算。

### 4.1 傳輸量計算 (Volume 計算邏輯)
目的：計算在查詢時間視窗內的資料傳輸總量，單位轉換為 MB。
* **計算公式**:
  * 對於每一筆 flow，若存在區間變動位元數 (Interval Bytes)，優先使用區間數據：
    `delta_bytes = (dst_dbo 或者 dbo 或者 0) + (dst_dbi 或者 dbi 或者 0)`
  * 若 `delta_bytes > 0`，則 `Volume (MB) = delta_bytes / 1024 / 1024`
  * 否則，使用歷史總位元數 (Total Bytes) 作為備用計算：
    `tbo = (dst_tbo 或者 tbo 或者 dst_bo 或者 0)`
    `tbi = (dst_tbi 或者 tbi 或者 dst_bi 或者 0)`
    `Volume (MB) = (tbo + tbi) / 1024 / 1024`

### 4.2 頻寬計算 (Bandwidth 計算邏輯)
目的：計算資料在此次連線期間的最高傳輸速率，單位為 Mbps。
* **計算公式**:
  * 同樣優先使用區間變動位元數 (`delta_bytes`)。
  * 取得區間持續毫秒數 `ddms`。
  * 若 `delta_bytes > 0` 且 `ddms > 0`:
    `Bandwidth (Mbps) = (delta_bytes * 8.0) / (ddms / 1000.0) / 1000000.0`
  * 若上式為 0，改用總位元數計算平均速率：
    取得總位元數 `total_bytes = tbo + tbi`。
    取得總持續毫秒數 `tdms`。若 `tdms < 1000` 則使用 `interval_sec` 取代 (`tdms = interval_sec * 1000`)。
    `Bandwidth (Mbps) = (total_bytes * 8.0) / (tdms / 1000.0) / 1000000.0`

### 4.3 連線數與資料聚合 (Aggregation)
* 每一筆流量過濾與計算完成後，需依據其特徵建立唯一的 **Aggregation Key**。
  * `Key Format`: `{Source Name} -> {Destination Name} [{Destination Port}]`
  * (註：若無 Workload Name，則顯示 IP 地址)
* 針對同一個 Key，需要：
  * **連線數 (Connection Count)**：加總每一筆流量的 `num_connections` (或 `count`)。
  * **傳輸量 (Volume)**：加總計算出來的 Volume。
  * **頻寬 (Bandwidth)**：取所有紀錄中的 **最大值 (Max)**，而不是加總 (不能疊加不同時間片段的最大速率)。

---

