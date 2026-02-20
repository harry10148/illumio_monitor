#!/usr/bin/env python3
try:
    from src.main import main_menu
    if __name__ == "__main__":
        main_menu()
except ImportError as e:
    print(f"Error importing src package: {e}")
    print("Ensure you are running this script from the parent directory of 'src'.")

