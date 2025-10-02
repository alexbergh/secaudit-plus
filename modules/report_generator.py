# modules/report_generator.py
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from pathlib import Path
import json
import platform
import socket
from collections import defaultdict
from collections.abc import Mapping, Sequence

def _normalize_fstek_code(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    text = text.upper()
    for token in ("ФСТЭК", "FSTEK", "МЕРА", "MEASURE"):
        text = text.replace(token, "")
    text = text.replace("№", "")
    for ch in ("-", "_", ",", ";", ":"):
        text = text.replace(ch, ".")
    text = text.strip(".")
    if not text:
        return None
    if "." not in text:
        for idx, char in enumerate(text):
            if char.isdigit():
                text = f"{text[:idx]}.{text[idx:]}"
                break
    while ".." in text:
        text = text.replace("..", ".")
    text = text.strip(".")
    return text or None


def _extract_fstek_codes(result):
    tags = None
    if isinstance(result, Mapping):
        tags = result.get("tags")
    else:
        tags = getattr(result, "tags", None)

    if not isinstance(tags, Mapping):
        return []

    raw = tags.get("fstec")
    if raw is None:
        return []

    if isinstance(raw, (str, bytes)):
        values = [raw]
    elif isinstance(raw, Mapping):
        values = [raw]
    elif isinstance(raw, Sequence):
        values = list(raw)
    else:
        values = [raw]

    codes = []
    seen = set()
    for item in values:
        candidate = None
        if isinstance(item, Mapping):
            for key in ("code", "id", "name", "value"):
                if item.get(key):
                    candidate = item[key]
                    break
        else:
            candidate = item

        code = _normalize_fstek_code(candidate)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    return codes

def generate_report(profile: dict, results: list, template_name: str, output_path: str):
    env = Environment(loader=FileSystemLoader("reports/"))
    env.filters["fstek_codes"] = _extract_fstek_codes

    template = env.get_template(template_name)

    pass_count = sum(1 for r in results if r["result"] == "PASS")
    fail_count = sum(1 for r in results if r["result"] == "FAIL")
    warn_count = sum(1 for r in results if r["result"] == "WARN")

    host_info = _collect_host_metadata(profile, results)

    rendered = template.render(
        profile=profile,
        results=results,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        host=host_info,
        host_info=host_info,
        FSTEK21=FSTEK21_DESCRIPTIONS,
        pass_count=pass_count,
        fail_count=fail_count,
        warn_count=warn_count
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

def generate_json_report(results: list, output_path: str):
    grouped = defaultdict(list)
    for r in results:
        module = r.get("module", "core")
        grouped[module].append(r)

    # Преобразуем defaultdict в обычный dict для JSON-сериализации
    grouped_dict = dict(grouped)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(grouped_dict, f, indent=2, ensure_ascii=False)
