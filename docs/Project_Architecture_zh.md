# Illumio PCE Monitor - 專案架構

> **[English](Project_Architecture.md)** | **[繁體中文](Project_Architecture_zh.md)**

## 概覽
**Illumio PCE Monitor** 是一個基於 Python 的應用程式，專為與 Illumio Core REST API (V2, 支援 Illumio 25.2) 互動而設計。它提供無人值守背景監控、互動式 CLI 設定，以及輕量級的 Flask Web GUI。
其核心目標是從 Illumio 串流獲取流量與事件日誌，利用使用者定義的門檻（連線數、頻寬、總傳輸量）進行評估，並產生告警（Webhook, Email, LINE）。

---

## 目錄與檔案結構

```text
illumio_monitor/
├── src/
│   ├── main.py        # 進入點。CLI 參數解析與 Daemon 迴圈管理。
│   ├── config.py      # 管理 settings.json（憑證、載入的規則、Email 設定）。
│   ├── api_client.py  # Illumio REST API 封裝，具備自動重試與串流特性。
│   ├── analyzer.py    # 核心邏輯引擎，對比 API 返回資料與設定規則。
│   ├── reporter.py    # 負責輸出和告警彙整（SMTP, Webhook, LINE APIs）。
│   ├── gui.py         # Flask Web 應用程式路由與供前端使用的 API 後端。
│   ├── settings.py    # CLI 互動選單，負責規則的 CRUD 操作。
│   ├── utils.py       # 輔助函式（色彩常數、位元組字串處理）。
│   ├── i18n.py        # 多國語言 (I18N) 翻譯字典與當前語言邏輯。
│   ├── templates/     # 包含 HTML 前端樣板檔案（例如 index.html）。
│   └── static/        # 包含 CSS/JS 前端檔案（預留區）。
├── docs/              # 擷取的 API 文件與架構文件。
├── logs/              # 應用程式執行日誌。
└── tests/             # Pytest 框架及測試邏輯驗證。
```

---

## 核心元件分析

### 1. `api_client.py` - 資料擷取
- 完全依賴 Python 內建的 `urllib.request`（無外部 `requests` 套件相依性）。
- 處理 Illumio 的**非同步流量查詢** (`/api/v2/orgs/{org_id}/traffic_flows/async_queries`)。
- **記憶體最佳化：** 由於流量查詢可能返回數 GB 的資料，此元件採用 Python 產生器 (`yield`) 搭配 gzip 解壓縮逐塊傳遞資料，確保在大流量匯入時維持 O(1) 的記憶體消耗。
- 內建指數退避 (Exponential Backoff) 重試機制，應對 API 的 429 (Rate Limits) 與 500 錯誤。

### 2. `analyzer.py` - 引擎
- 將 `api_client` 擷取的資料包與 `config.py` 中定義的規則進行驗證比對。
- 計算即時頻寬與累計總傳輸量。
- 透過儲存於本地的 `state.json` 評估**門檻值**與**冷卻時間**。
- **高效能本地端過濾**：一次性向 PCE 查詢所有規則中所需的最長監控視窗，後續全部在記憶體內執行子過濾器邏輯。
- 應用 `tempfile.mkstemp` 及 `os.replace`，確保儲存 `state.json` 時採**原子性寫入 (Atomic Writes)**，防止 Daemon 中斷造成的資料損毀。

### 3. `reporter.py` - 告警發送子系統
- 將監測指標分為：健康度檢查、安全事件、流量數，及傳輸量告警。
- 針對不同輸出通道格式化內容：CLI/Log (純文字)、Webhooks (JSON 結構)、Email (HTML 表格)。
- 具備 Webhook 保護機制，使用設定的超時限制與異常捕捉來防範外部服務斷線。

### 4. `gui.py` - 使用者介面
- **後端：** 透過 Flask 提供供 AJAX 呼叫的 JSON API 端點（例如 `/api/rules`, `/api/dashboard/top10`），並整合了子程序捕捉技術，讓 Web UI 也能執行 CLI 上的「Debug 模式」。
- **前端：** 以純淨的方式抽出為 `templates/index.html`。利用原生 JavaScript 的 `fetch()` 函式直接與 Flask 的 JSON 後端溝通。具備免重整即可切換的多國語言動態翻譯功能。

### 5. `tests/` - 單元驗證
- 包含 `test_analyzer.py`，利用 `pytest` 執行全面性的測試。
- 用以模擬 Illumio API 回傳的大量 Json 結果，藉以強制驗證邊界邏輯（例如滑動時間視窗、冷卻時間重置與進階過濾器匹配度）。

---

## 近期重構與 Code Review 成果

本專案架構近期經過了嚴格的 Peer Review，成果已經整合如下：
1. **前端重構：** 已將 `gui.py` 內龐大的單體 HTML 區塊成功抽離至標準的 Jinja 架構 (`templates/index.html`)。
2. **原子化寫入：** 在 `analyzer.py` 中引入了原子性檔案置換策略，徹底修復 `state.json` 寫入途中被強制中斷導致的毀損漏洞。
3. **優化輪詢等待：** 移除 `main.py` Daemon 當中封閉式的 `time.sleep()` 延遲迴圈，並替換為 `threading.Event().wait()`，這使得使用者發出 SIGINT (Ctrl+C) 時，程式能立刻做出關閉反應而不是等待。
4. **測試驅動的驗證 (Test Driven Verification)：** 成功配置了 `pytest` 測試框架，確保核心分析引擎對流量 JSON 的解析及門檻評估在日後更新時不被破壞。
