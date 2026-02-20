#!/usr/bin/env python3
try:
    from illumio_monitor.main import main_menu
    if __name__ == "__main__":
        main_menu()
except ImportError as e:
    print(f"Error importing illumio_monitor package: {e}")
    print("Ensure you are running this script from the parent directory of 'illumio_monitor'.")

