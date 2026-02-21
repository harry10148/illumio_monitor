import sys
import os
import signal
import time
import logging
import argparse
from src import __version__
from src.utils import setup_logger, Colors, safe_input
from src.config import ConfigManager
from src.api_client import ApiClient
from src.analyzer import Analyzer
from src.reporter import Reporter
from src.settings import (
    settings_menu,
    add_event_menu,
    add_traffic_menu,
    add_bandwidth_volume_menu,
    manage_rules_menu
)
from src.i18n import t

logger = logging.getLogger(__name__)

# ─── Daemon / Monitor Loop ───────────────────────────────────────────────────

_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    logger.info(f"Received signal {signum}. Shutting down gracefully...")


def run_daemon_loop(interval_minutes: int):
    """Headless monitoring loop. Runs analysis at fixed intervals until stopped."""
    global _shutdown_requested
    _shutdown_requested = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    cm = ConfigManager()
    logger.info(f"Starting daemon loop (interval={interval_minutes}m)")
    print(f"Illumio PCE Monitor — daemon mode (interval={interval_minutes}m)")
    print("Press Ctrl+C or send SIGTERM to stop.")

    while not _shutdown_requested:
        try:
            logger.info("=== Starting monitoring cycle ===")
            api = ApiClient(cm)
            rep = Reporter(cm)
            ana = Analyzer(cm, api, rep)
            ana.run_analysis()
            rep.send_alerts()
            logger.info("=== Monitoring cycle completed ===")
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}", exc_info=True)

        # Sleep in small increments so we can respond to shutdown quickly
        sleep_seconds = interval_minutes * 60
        for _ in range(sleep_seconds):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger.info("Daemon loop stopped.")
    print("\nDaemon stopped.")


# ─── Interactive CLI Menu ─────────────────────────────────────────────────────

def main_menu():
    # Setup Logging
    PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(PKG_DIR)
    LOG_DIR = os.path.join(ROOT_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'illumio_monitor.log')

    setup_logger('illumio_monitor', LOG_FILE)
    logger.info("Starting Illumio PCE Monitor")

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
        print(t('main_menu_10').replace('{Colors.CYAN}', Colors.CYAN).replace('{Colors.ENDC}', Colors.ENDC))
        print(t('main_menu_0'))

        sel = safe_input(f"\n{t('please_select')}", int, range(0, 11))

        if sel == 0:
            break
        elif sel == 1:
            add_event_menu(cm)
        elif sel == 2:
            add_traffic_menu(cm)
        elif sel == 3:
            add_bandwidth_volume_menu(cm)
        elif sel == 4:
            manage_rules_menu(cm)
        elif sel == 5:
            settings_menu(cm)
        elif sel == 6:
            print(f"\n{Colors.WARNING}{t('warning_best_practices')}{Colors.ENDC}")
            confirm = safe_input(f"{t('confirm_continue')} (Y/N)", str)
            if confirm and confirm.strip().upper() == 'Y':
                cm.load_best_practices()
                input(t('best_practice_loaded', default='\nBest practices loaded successfully! Press Enter to continue...'))
            else:
                input(t('operation_cancelled', default='\nOperation cancelled. Press Enter to continue...'))
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
        elif sel == 10:
            # Launch Web GUI from console menu
            from src.gui import launch_gui, HAS_FLASK
            if not HAS_FLASK:
                print(f"{Colors.FAIL}Web GUI not available: Flask is not installed.{Colors.ENDC}")
                print(f"  Install it with: pip install flask")
                input(t('press_enter_to_continue'))
            else:
                port_str = safe_input("Web GUI Port (default 5001): ", str)
                try:
                    port = int(port_str) if port_str and port_str.strip() else 5001
                except (ValueError, TypeError):
                    port = 5001
                launch_gui(cm, port=port)


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Illumio PCE Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python illumio_monitor.py                       # Interactive CLI menu\n"
            "  python illumio_monitor.py --monitor             # Headless daemon mode\n"
            "  python illumio_monitor.py --monitor -i 5        # Daemon with 5-min interval\n"
            "  python illumio_monitor.py --gui                 # Launch Web GUI (port 5001)\n"
            "  python illumio_monitor.py --gui --port 8080     # Web GUI on custom port\n"
        )
    )
    parser.add_argument('--monitor', action='store_true',
                        help='Run in headless daemon mode (no interactive menu)')
    parser.add_argument('-i', '--interval', type=int, default=10,
                        help='Monitoring interval in minutes (default: 10)')
    parser.add_argument('--gui', action='store_true',
                        help='Launch the Web GUI (requires: pip install flask)')
    parser.add_argument('-p', '--port', type=int, default=5001,
                        help='Web GUI port (default: 5001)')

    args = parser.parse_args()

    # Setup logging early for all modes
    PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(PKG_DIR)
    LOG_DIR = os.path.join(ROOT_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_DIR, 'illumio_monitor.log')
    setup_logger('illumio_monitor', LOG_FILE)

    if args.monitor:
        run_daemon_loop(args.interval)
    elif args.gui:
        from src.gui import launch_gui, HAS_FLASK
        if not HAS_FLASK:
            print("Web GUI requires Flask. Install it with:")
            print("  pip install flask")
            sys.exit(1)
        cm = ConfigManager()
        launch_gui(cm, port=args.port)
    else:
        try:
            main_menu()
        except KeyboardInterrupt:
            print(f"\n{t('bye_msg')}")


if __name__ == "__main__":
    main()
