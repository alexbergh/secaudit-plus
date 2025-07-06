# modules/os_detect.py

from pathlib import Path
import re

def detect_os() -> str:
    osr_path = Path("/etc/os-release")
    if not osr_path.exists():
        return "unknown"

    with osr_path.open() as f:
        data = f.read()

    def get_field(field):
        match = re.search(rf'{field}="?([^"\n]+)"?', data)
        return match.group(1).lower() if match else ""

    os_id = get_field("ID")
    os_like = get_field("ID_LIKE")

    if "astra" in os_id or "astra" in os_like:
        return "astra"
    elif "alt" in os_id:
        return "alt"
    elif "centos" in os_id or "rhel" in os_like:
        return "centos"
    elif "debian" in os_like or "ubuntu" in os_id:
        return "debian"
    else:
        return "unknown"
