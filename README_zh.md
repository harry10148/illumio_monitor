# Illumio PCE Monitor

![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square&logo=python&logoColor=white)

> **[English](README.md)** | **[繁體中文](README_zh.md)**

專為 **Illumio Core (PCE)** 設計的進階**無 Agent (Agentless)** 監控工具。透過 REST API 實現智慧型流量分析、安全事件偵測與自動化告警。**無需安裝外部套件**（CLI/Daemon 模式僅使用 Python 標準函式庫）。

具備強大的背景無人值守 Daemon、互動式 CLI 文字選單，以及本地架設的 Web GUI 視覺化介面。

---

## 📖 文件目錄

為保持專案版面簡潔易讀，詳細的操作與開發文件已分類至以下專屬頁面：

*   **[完整使用手冊 (User Manual)](docs/User_Manual_zh.md)**: 包含安裝、三種執行模式詳解、如何設置各項告警與規則的詳細引導。
*   **[專案架構與 Code Review (Project Architecture)](docs/Project_Architecture_zh.md)**: 深入剖析程式碼設計、API 連線記憶體最佳化策略，以及近期的 Code Review 優化成果。

---

## ✨ 核心特色

1.  **三種執行模式**: 支援背景守護程序 (`--monitor`)、手動 CLI 互動精靈，或是基於 Flask 的漂亮 **Web GUI 網頁控制台** (`--gui`)。
2.  **保證不重複的事件監控**: 嚴密追蹤 PCE 上的稽核日誌。採用絕對時間戳記錨點，保證您絕對不會收到任何一筆重複發生的安全告警。
3.  **高效能流量引擎**: 將您的多條流量規則整合為一次大範圍的 API 查詢，並在本地端記憶體（O(1) 消耗）中完成龐大連線資料的解析作業，徹底杜絕對 PCE 發動連續呼叫的負擔。
4.  **多通道即時告警**: 同步支援透過 **Email (SMTP)**、**LINE 通知** 與 **Webhooks** 派發告警。
5.  **多語系介面**: 在 Web GUI 當中，可隨時一秒即時切換英文與繁體中文，無須重新載入。

---

## 🚀 快速開始

### 1. 系統需求
*   **Python 3.8+**
*   (若需使用 Web GUI 才需安裝): `pip install flask`

### 2. 啟動方式
複製專案，建立設定檔後即可執行：

```bash
git clone <repo-url>
cd illumio_monitor
cp config.json.example config.json    # 請編輯並填入您的 PCE 憑證

# 互動式 CLI:
python illumio_monitor.py             

# Web 視覺化圖形介面（自動開啟瀏覽器導向 http://127.0.0.1:5001）:
python illumio_monitor.py --gui       

# 背景 Daemon 模式（每 5 分鐘於背景自動執行監控一次）:
python illumio_monitor.py --monitor --interval 5
```

如需進階的 Windows 服務 (NSSM) 封裝或 Linux (systemd) 背景部署方式，請參閱 **[完整使用手冊](docs/User_Manual_zh.md)**。
