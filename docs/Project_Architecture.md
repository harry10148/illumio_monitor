# Illumio PCE Monitor - Project Architecture

## Overview
The **Illumio PCE Monitor** is a Python-based application designed to interact with the Illumio Core REST API (V2, currently compliant with Illumio 25.2). It provides headless monitoring, interactive CLI configuration, and a lightweight Flask Web GUI.
Its core purpose is to stream traffic flow data and event logs from Illumio, evaluate them against user-defined thresholds (Connection count, Bandwidth, Total Volume), and generate alerts (Webhook, Email, LINE).

---

## Directory & File Structure

```text
illumio_monitor/
├── src/
│   ├── main.py        # Entry point. CLI argument parser and daemon loop manager.
│   ├── config.py      # Manages settings.json (credentials, loaded rules, email config).
│   ├── api_client.py  # Illumio REST API abstraction with auto-retry and streaming.
│   ├── analyzer.py    # Core logic engine assessing API return data against Rules.
│   ├── reporter.py    # Handles output/alerting aggregation (SMTP, Webhook, LINE APIs).
│   ├── gui.py         # Flask Web Application routes and API backend for the frontend.
│   ├── settings.py    # CLI Interactive Menus for CRUD operations on rules.
│   ├── utils.py       # Helper functions (color constants, byte string matchers).
│   ├── i18n.py        # I18N Translation dict and active language logic.
│   ├── templates/     # Contains Jinja2/HTML frontend files (e.g. index.html)
│   └── static/        # Contains CSS/JS frontend files (reserved)
├── docs/              # Extracted API docs & Review metrics
├── logs/              # Runtime application logs
└── tests/             # Pytest framework (Optional / In-Development)
```

---

## Core Components Analysis

### 1. `api_client.py` - The Data Fetches
- Uses native `urllib.request` (no external `requests` dependency).
- Handles Illumio's **Asynchronous Traffic Flow Queries** (`/api/v2/orgs/{org_id}/traffic_flows/async_queries`).
- **Memory Optimization:** Since traffic queries can return gigabytes of data, it utilizes Python generators (`yield`) passing chunks wrapped through gzip decompression. This ensures O(1) memory during high-flow ingestion.

### 2. `analyzer.py` - The Engine
- Validates data packets fetched by `api_client` against rules defined in `config.py`.
- Computes Bandwidth (Interval / Total).
- Evaluates **Thresholds** and **Cooldowns** via a saved local state file (`state.json`).
- Uses `tempfile.mkstemp` and `os.replace` to guarantee atomic writes of `state.json` even during interruptions.

### 3. `reporter.py` - The Alerting Sub-System
- Separates metrics into Health, Events, Traffic, and Volume alerts.
- Formats output depending on the endpoint: pure ASCII limits for CLI/Log, JSON structures for Webhooks, HTML tables for Email. 
- Built-in URL validation and `TimeoutError` resilience.

### 4. `gui.py` - The Interface
- **Backend:** Flask exposing JSON endpoints (e.g., `/api/rules`, `/api/dashboard/top10`). Uses `os.fdopen` style system capture to port the `runDebug()` CLI analyzer straight to the Web console.
- **Frontend:** Found in `templates/index.html`. Built originally as an embedded Single Page App (SPA). Uses Vanilla JS `fetch()` to manipulate the Flask JSON backend.
