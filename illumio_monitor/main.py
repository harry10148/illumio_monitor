import sys
import os
import logging
from . import __version__
from .utils import setup_logger
from .config import ConfigManager
from .api_client import ApiClient
from .analyzer import Analyzer
from .reporter import Reporter
from .utils import Colors, safe_input
from .utils import Colors, safe_input
from .settings import (
    settings_menu, 
    add_event_menu, 
    add_traffic_menu, 
    add_bandwidth_volume_menu, 
    manage_rules_menu
)
def main_menu():
    # Setup Logging
    # Root dir is the parent of the package directory (illumio_monitor)
    PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(PKG_DIR) 
    LOG_DIR = os.path.join(ROOT_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'illumio_monitor.log')
    
    logger = setup_logger('illumio_monitor', LOG_FILE)
    logger.info(f"Starting Illumio PCE Monitor v{__version__}")

    cm = ConfigManager()
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Colors.HEADER}=== Illumio PCE Monitor v{__version__} ==={Colors.ENDC}")
        print(f"API: {cm.config['api']['url']} | Rules: {len(cm.config['rules'])}")
        print("-" * 40)
        print("1. 新增事件規則 (含 PCE Health Check)")
        print(f"2. 新增{Colors.WARNING}流量規則 (Traffic Rule){Colors.ENDC}")
        print(f"3. 新增{Colors.CYAN}頻寬與傳輸量規則 (Bandwidth & Volume){Colors.ENDC}")
        print("4. 管理規則 (列表/刪除)")
        print("5. 系統設定 (API / Email)")
        print(f"{Colors.CYAN}6. 載入官方最佳實踐 (Best Practices){Colors.ENDC}")
        print("7. 發送測試信件")
        print("8. 立即執行監控 (Run Once)")
        print(f"9. 流量規則模擬與除錯 (Debug Mode)")
        print("0. 離開")
        
        sel = safe_input("\n請選擇", int, range(0, 10))
        
        if sel == 0: break
        elif sel == 1: add_event_menu(cm)
        elif sel == 2: add_traffic_menu(cm)
        elif sel == 3: add_bandwidth_volume_menu(cm)
        elif sel == 4: manage_rules_menu(cm)
        elif sel == 5: settings_menu(cm)
        elif sel == 6: 
            print(f"\n{Colors.WARNING}警告: 此操作將清除所有現有規則並載入官方建議設定。{Colors.ENDC}")
            confirm = safe_input("確定要繼續嗎? (輸入 'YES' 確認)", str)
            if confirm == 'YES':
                cm.load_best_practices()
                input("Best practices loaded. Press Enter...")
            else:
                input("Operation cancelled. Press Enter...")
        elif sel == 7: 
            Reporter(cm).send_email(force_test=True)
            input("Done.")
        elif sel == 8:
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_analysis()
            rep.send_email()
            input("Done.")
        elif sel == 9:
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_debug_mode()
            input("Debug Done. Press Enter...")

if __name__ == "__main__":
    try: main_menu()
    except KeyboardInterrupt: print("\nBye.")
