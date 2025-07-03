# modules/bash_executor.py
import subprocess

def run_bash(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"
