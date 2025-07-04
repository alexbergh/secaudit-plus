# main.py
from modules.audit_runner import load_profile, run_checks
from modules.report_generator import generate_report
from utils.logger import log_info, log_pass, log_fail, log_warn
import json
from pathlib import Path

def main():
    log_info("Загрузка профиля")
    profile = load_profile("profiles/baseline.yml")

    log_info(f"Аудит профиля: {profile['profile_name']}")
    results = run_checks(profile)

    Path("results").mkdir(exist_ok=True)
    with open("results/report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # CLI вывод
    for r in results:
        if r["result"] == "PASS":
            log_pass(f"{r['name']} → {r['output']}")
        elif r["result"] == "FAIL":
            log_fail(f"{r['name']} → {r['output']}")
        else:
            log_warn(f"{r['name']} → {r['output']}")

    # Отчёты
    log_info("Генерация Markdown отчёта)
    generate_report(profile, results, "report_template.md.j2", "results/report.md")

    log_info("Генерация HTML отчёта")
    generate_report(profile, results, "report_template.html.j2", "results/report.html")

if __name__ == "__main__":
    main()
