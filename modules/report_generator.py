# modules/report_generator.py
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from pathlib import Path

def generate_report(profile: dict, results: list, template_name: str, output_path: str):
    env = Environment(loader=FileSystemLoader("reports/"))
    template = env.get_template(template_name)

    pass_count = sum(1 for r in results if r["result"] == "PASS")
    fail_count = sum(1 for r in results if r["result"] == "FAIL")
    warn_count = sum(1 for r in results if r["result"] == "WARN")

    rendered = template.render(
        profile=profile,
        results=results,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
