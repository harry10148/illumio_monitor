# Illumio PCE Monitor

![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square&logo=python&logoColor=white)

> **[English](README.md)** | **[繁體中文](README_zh.md)**

An advanced **agentless** monitoring tool for **Illumio Core (PCE)** via REST API. Features intelligent traffic analysis, security event detection, and automated alerting — with **zero external dependencies** (Python stdlib only for CLI/daemon modes).

Provides a comprehensive headless daemon for unmonitored execution, an interactive CLI, and a locally-hosted Web GUI.

---

## 📖 Documentation Directory

To keep this repository clean and maintainable, detailed documentation is split into dedicated files.

*   **[User Manual](docs/User_Manual.md)**: Detailed instructions on installation, execution modes, configuring alerts, and creating Event/Traffic rules.
*   **[Project Architecture & Code Review](docs/Project_Architecture.md)**: Deep dive into the codebase design, API consumption strategies, memory optimization, and recent code review refinements.

---

## ✨ Key Features

1.  **Triple Execution Modes**: Choose between a background daemon (`--monitor`), a CLI interactive wizard, or a Flask-powered visual **Web GUI** (`--gui`).
2.  **No-Spam Event Monitoring**: Tracks PCE audit events securely. Utilizes strictly anchor-based timestamps to guarantee you never receive duplicate alerts for the same event.
3.  **High-Performance Traffic Engine**: Aggregates configured rules to perform a single, time-based bulk query against the PCE. Processes the heavy data streams exclusively within local memory (O(1) memory ingestion) instead of spamming the API.
4.  **Multi-Channel Alerts**: Synchronously dispatches alerts via **Email (SMTP)**, **LINE Notifications**, and **Webhooks**.
5.  **Multi-Language UI**: Instantly leap between English and Traditional Chinese within the Web GUI without reloading the system.

---

## 🚀 Quick Start

### 1. Requirements
*   **Python 3.8+**
*   (Optional for Web GUI): `pip install flask`

### 2. Launch
Clone the project, copy the example config, and run:

```bash
git clone <repo-url>
cd illumio_monitor
cp config.json.example config.json    # Edit with your PCE credentials

# Interactive CLI:
python illumio_monitor.py             

# Visual Web GUI (Automatically opens browser map to http://127.0.0.1:5001):
python illumio_monitor.py --gui       

# Background Daemon mode (Checks every 5 minutes):
python illumio_monitor.py --monitor --interval 5
```

For advanced Windows Service (NSSM) or Linux (systemd) deployments, please refer to the **[User Manual](docs/User_Manual.md)**.
