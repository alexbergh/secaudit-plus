# main.py
from modules.audit_runner import load_profile, run_checks
import json
from pathlib import Path

def main():
    profile = load_profile("profiles/baseline.yml")
    results = run_checks(profile)
    Path("results").mkdir(exist_ok=True)
    with open("results/report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    for r in results:
        print(f"[{r['result']}] {r['name']} → {r['output']}")

if __name__ == "__main__":
    main()
