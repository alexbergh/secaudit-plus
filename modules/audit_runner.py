# modules/audit_runner.py
import yaml
from modules.bash_executor import run_bash

def load_profile(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

def run_checks(profile: dict) -> list:
    results = []
    for check in profile['checks']:
        output = run_bash(check['command'])
        status = "PASS" if check['expect'] in output else "FAIL"
        results.append({
            "id": check["id"],
            "name": check["name"],
            "result": status,
            "output": output,
            "severity": check["severity"]
        })
    return results
