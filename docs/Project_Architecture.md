# Illumio PCE Monitor - Project Architecture

> **[English](Project_Architecture.md)** | **[繁體中文](Project_Architecture_zh.md)**

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
│   ├── templates/     # Contains HTML frontend templates (e.g. index.html)
│   └── static/        # Contains CSS/JS frontend files (reserved)
├── docs/              # Extracted API docs & Review metrics
├── logs/              # Runtime application logs
└── tests/             # Pytest framework logic validation
```

---

## Core Components Analysis

### 1. `api_client.py` - The Data Fetches
- Uses native `urllib.request` (no external `requests` dependency).
- Handles Illumio's **Asynchronous Traffic Flow Queries** (`/api/v2/orgs/{org_id}/traffic_flows/async_queries`).
- **Memory Optimization:** Since traffic queries can return gigabytes of data, it utilizes Python generators (`yield`) passing chunks wrapped through gzip decompression. This ensures O(1) memory ingestion.
- Built-in robustness with exponential backoff for 429s (Rate Limits) and 500s.

### 2. `analyzer.py` - The Engine
- Validates data packets fetched by `api_client` against rules defined in `config.py`.
- Computes Bandwidth (Interval / Total).
- Evaluates **Thresholds** and **Cooldowns** via a saved local state file (`state.json`).
- High-Performance local filtering: Exclusively queries the PCE for maximum sliding windows and filters flows logically in-memory against rule subsets.
- Uses `tempfile.mkstemp` and `os.replace` to guarantee **atomic writes** of `state.json` ensuring no data corruption upon daemon interruptions.

### 3. `reporter.py` - The Alerting Sub-System
- Separates metrics into Health, Events, Traffic, and Volume alerts.
- Formats output depending on the endpoint: pure ASCII limits for CLI/Log, JSON structures for Webhooks, HTML tables for Email. 
- Integrated Webhook resilience utilizing active timeouts and fallback handlers.

### 4. `gui.py` - The Interface
- **Backend:** Flask exposing JSON endpoints (e.g., `/api/rules`, `/api/dashboard/top10`). Provides sub-process stdout manipulation for the Web UI.
- **Frontend:** Extracted cleanly into `templates/index.html`. Uses Vanilla JS `fetch()` to manipulate the Flask JSON backend. Offers dynamic localized translations without reloading.

### 5. `tests/` - Validation
- Contains `test_analyzer.py` executing comprehensive unit testing via `pytest`.
- Emulates the Illumio API responses to strictly test boundary logic (Sliding windows, Cooldown resets, Match filters).

---

## Recent Refactoring & Code Review Outcomes

The project architecture has recently undergone strict peer review resulting in key enhancements mapped out below:
1. **Frontend Refactoring:** Extracted monolithic inline HTML blocks from `gui.py` into native standard Jinja frameworks (`templates/index.html`).
2. **Atomic Writes:** Resolved the `state.json` corruption vulnerability by deploying atomic replacement strategies in `analyzer.py`.
3. **Optimized Polling:** Removed static `time.sleep()` blockers from `main.py` daemon, replacing with `threading.Event().wait()` permitting instantaneous shutdown interception via SIGINT.
4. **Test Driven Verification:** Established `pytest` to guarantee rule parsing constraints are respected continuously against mock traffic.
