import os
import logging
from logging.handlers import RotatingFileHandler
from src.i18n import t

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

def safe_input(prompt: str, value_type=str, valid_range=None, allow_cancel=True, hint=None):
    full_prompt = f"{prompt} {Colors.CYAN}{hint}{Colors.ENDC}: " if hint else f"{prompt}: "
    while True:
        try:
            raw = input(full_prompt)
            if not raw.strip():
                if allow_cancel: return None
                else: continue
            if raw.strip() == '-1' and allow_cancel: return None
            val = value_type(raw)
            if valid_range and val not in valid_range:
                print(f"{Colors.FAIL}{t('error_out_of_range', default='數值超出範圍。')}{Colors.ENDC}")
                continue
            return val
        except ValueError: print(f"{Colors.FAIL}{t('error_format', default='格式錯誤。')}{Colors.ENDC}")

def setup_logger(name: str, log_file: str, level=logging.INFO, max_bytes: int = 10*1024*1024, backup_count: int = 5) -> logging.Logger:
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers: logger.addHandler(handler)
    return logger

def format_unit(value, type='volume') -> str:
    try: val = float(value)
    except: return str(value)
    
    if type == 'volume': 
        if val >= 1024 * 1024: return f"{val/(1024*1024):.2f} TB"
        if val >= 1024: return f"{val/1024:.2f} GB"
        return f"{val:.2f} MB"
    elif type == 'bandwidth': 
        if val >= 1000: return f"{val/1000:.2f} Gbps"
        return f"{val:.2f} Mbps"
    return str(val)
