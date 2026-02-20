@echo off
cd /d "%~dp0"
echo 8 | python monitor_wrapper.py >> logs\illumio_monitor.log 2>&1
