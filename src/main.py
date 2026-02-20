import sys
import os
import logging
from src import __version__
from src.utils import setup_logger
from src.config import ConfigManager
from src.api_client import ApiClient
from src.analyzer import Analyzer
from src.reporter import Reporter
from src.utils import Colors, safe_input
from src.settings import (
    settings_menu, 
    add_event_menu, 
    add_traffic_menu, 
    add_bandwidth_volume_menu, 
    manage_rules_menu
)
from src.i18n import t

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
        print(f"{Colors.HEADER}=== Illumio PCE Monitor ==={Colors.ENDC}")
        print(f"API: {cm.config['api']['url']} | Rules: {len(cm.config['rules'])}")
        print("-" * 40)
        print(t('main_menu_1'))
        print(t('main_menu_2').replace('{Colors.WARNING}', Colors.WARNING).replace('{Colors.ENDC}', Colors.ENDC))
        print(t('main_menu_3').replace('{Colors.CYAN}', Colors.CYAN).replace('{Colors.ENDC}', Colors.ENDC))
        print(t('main_menu_4'))
        print(t('main_menu_5'))
        print(t('main_menu_6').replace('{Colors.CYAN}', Colors.CYAN).replace('{Colors.ENDC}', Colors.ENDC))
        print(t('main_menu_7'))
        print(t('main_menu_8'))
        print(t('main_menu_9'))
        print(t('main_menu_0'))
        
        sel = safe_input(f"\n{t('please_select')}", int, range(0, 10))
        
        if sel == 0: break
        elif sel == 1: add_event_menu(cm)
        elif sel == 2: add_traffic_menu(cm)
        elif sel == 3: add_bandwidth_volume_menu(cm)
        elif sel == 4: manage_rules_menu(cm)
        elif sel == 5: settings_menu(cm)
        elif sel == 6: 
            print(f"\n{Colors.WARNING}{t('warning_best_practice')}{Colors.ENDC}")
            confirm = safe_input(t('confirm_best_practice'), str)
            if confirm == 'YES':
                cm.load_best_practices()
                input(t('best_practice_loaded'))
            else:
                input(t('operation_cancelled'))
        elif sel == 7: 
            Reporter(cm).send_alerts(force_test=True)
            input(t('done_msg'))
        elif sel == 8:
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_analysis()
            rep.send_alerts()
            print(t('done_msg'))
        elif sel == 9:
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_debug_mode()
            input(t('debug_done'))

if __name__ == "__main__":
    try: main_menu()
    except KeyboardInterrupt: print(f"\n{t('bye_msg')}")
