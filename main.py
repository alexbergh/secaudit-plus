from modules.cli import parse_args
from modules.os_detect import detect_os
from modules.audit_runner import load_profile, run_checks
from modules.report_generator import generate_report, generate_json_report
from utils.logger import log_info, log_warn, log_pass, log_fail
from pathlib import Path
import json

def main():
    args = parse_args()

    os_id = detect_os()
    log_info(f"Обнаружена ОС: {os_id}")

    profile_path = args.profile or f"profiles/{os_id}.yml"
    if not Path(profile_path).exists():
        log_warn(f"Профиль {profile_path} не найден. Используется common/baseline.yml")
        profile_path = "profiles/common/baseline.yml"

    log_info(f"Загрузка профиля: {profile_path}")
    profile = load_profile(profile_path)

    selected_modules = []
    if args.module:
        selected_modules = [m.strip() for m in args.module.split(",")]
        log_info(f"Выбраны модули: {selected_modules}")

    results = run_checks(profile, selected_modules)

    Path("results").mkdir(exist_ok=True)

    # Полный список результатов (плоский)
    with open("results/report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Группировка результатов по модулям в отдельный JSON
    generate_json_report(results, "results/report_grouped.json")

    for r in results:
        if r["result"] == "PASS":
            log_pass(f"{r['name']} → {r['output']}")
        elif r["result"] == "FAIL":
            log_fail(f"{r['name']} → {r['output']}")
        else:
            log_warn(f"{r['name']} → {r['output']}")

    generate_report(profile, results, "report_template.md.j2", "results/report.md")
    generate_report(profile, results, "report_template.html.j2", "results/report.html")

if __name__ == "__main__":
    main()
