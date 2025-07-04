# utils/logger.py
from colorama import init, Fore, Style

init(autoreset=True)

def log_info(msg):
    print(Fore.CYAN + "[INFO] " + Style.RESET_ALL + msg)

def log_pass(msg):
    print(Fore.GREEN + "[PASS] " + Style.RESET_ALL + msg)

def log_fail(msg):
    print(Fore.RED + "[FAIL] " + Style.RESET_ALL + msg)

def log_warn(msg):
    print(Fore.YELLOW + "[WARN] " + Style.RESET_ALL + msg)

def log_error(msg):
    print(Fore.MAGENTA + "[ERROR] " + Style.RESET_ALL + msg)
