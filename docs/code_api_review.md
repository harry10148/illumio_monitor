# Illumio Monitor API Code Review (REST APIs 25.2)

## 總覽 Overview
本文檔為 AI 開發筆記，目的是記錄系統化 Code Review 的結果，特別是確認目前的 codebase 針對 [Illumio REST APIs 25.2](/docs/REST_APIs_25_2.pdf) 的相容性與正確性。未來的 AI 代理可以無須重新解析 6.6MB 的龐大 PDF 官方文檔，直接參照此份文件接手開發、代碼改寫或除錯。

## 檢查過程
1. 利用腳本對 `REST_APIs_25_2.pdf` 進行關鍵字提取（擷取 `/events`, `/traffic_flows/async_queries`, `/health` 等端點文件）。
2. 與原始碼庫（特別是 `src/api_client.py` 及 `src/gui.py`）中的 HTTP Request 實作細節與參數驗證進行交叉比對。

## API 對比結果 (API Compatibility Review)
目前前端 GUI 與後端 Polling 引擎使用的 API 呼叫均符合 25.2 版本的規格：

### 1. PCE Health Check
- **Codebase 使用方式**: `GET /api/v2/health`
- **PDF 規格對應 (Page 135)**: 驗證無誤。規格指出 `GET [api_version]/health` 是標準端點。
- **實作狀態**: 正確實作，成功回傳 PCE Cluster 的 healthy 狀態。

### 2. Events API
- **Codebase 使用方式**: `GET /api/v2/orgs/{org_id}/events`
- **參數傳遞**: `timestamp[gte]`, `max_results`
- **PDF 規格對應 (Page 143-145)**: 驗證無誤。PDF 明確允許 `max_results` 參數來取得指定數量的 events (最大支援至 10000 筆，而代碼 `max_results=1000` 為安全預設值，完全合法且合規)。

### 3. Traffic Flows (Async Queries)
與一般同步查詢 `POST .../traffic_analysis_queries` (在 25.2 某些版本可能被 Deprecated) 不同，Codebase 採用的是進階的 **非同步查詢 (Asynchronous Queries)** API，這非常標準且具擴展性。

- **建立查詢 (POST)**
  - **Codebase**: `POST /api/v2/orgs/{org_id}/traffic_flows/async_queries`
  - **Payload Structure**: 包含 `query_name`, `sources`, `destinations`, `services`, `start_date`, `end_date`, `policy_decisions` 等參數。
  - **PDF 規格對應 (Page 283)**: 參數名稱結構與 JSON Body 對應無誤（`include` 與 `exclude` list）。特別注意 `pd` (Policy Decision) 列舉如：`0` (Allowed), `1` (Potentially Blocked), `2` (Blocked), `3` (Unknown)。
- **Polling (GET Job Status)**
  - 狀態 `completed` 與 `failed` 處理邏輯均有實作，且對應了 202 Accepted 回傳後 `href` 的定期輪詢確認機制。
- **Download Download**
  - **Codebase**: `GET /api/v2{job_url}/download`
  - 支援 Gzip 壓縮，以及 fallback 的 Line-delimited JSON 解析，完美對應 API Specification 針對大量日誌傳輸的要求。

## 邏輯狀態與防呆機制狀態 (Logic State & Robustness)
- **Retry Mechanism**: `src/api_client.py` 內建帶有 backoff 機制的 Retry（針對 HTTP 429 或 5xx Error），對於長時輪詢非常健康。
- **GZIP Decoding**: 支援解壓縮和錯誤忽略（跳過陣列開頭或逗號結尾造成的 JSONDecoreError），提高了資料流的容錯率。

## 未來 AI 開發與除錯指南 (Developer Guide for Future AIs)
1. **API 新增或替換**: 
   - 當需要新增 Illumio API 功能（如 Rule 增刪改）時，請參考本文檔所述，優先將新 API 加入 `src/api_client.py`。
   - 所有 Request 必須攜帶相同的 `Basic base64(key:secret)` Authorization headers。
2. **流量查詢過濾**:
   - `services`, `sources`, `destinations` 參數若為空，根據 API 文檔，表示包含全部 ("ANY" 或 "ALL")。這點與目前程式邏輯相符。
3. **Policy Decision (pd) 識別**:
   - GUI 常常過濾 `pd=2` 作為異常與警報。若未來業務邏輯需要警報「未知 (Unknown)」流量，請將 `pd=3` 加入過濾器中。
4. **效能優化建議**:
   - 當前的 `extract_api_docs.py` 已經將 25.2 重點 PDF 萃取為 `/docs/extracted_api_docs.txt`，請優先參考該純文字檔以節省 Tokens 消耗。

## 結論 
**目前的 Codebase 架構、邏輯狀態以及針對 Illumio REST APIs 25.2 的 API 呼叫，全部正確且非常穩定。** 無須做任何即時的大規模重構。所有的規格皆無縫接軌。
