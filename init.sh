#!/bin/bash

set -e

echo "[+] Инициализация проекта SecAudit-core..."

mkdir -p secaudit-core/{modules,profiles,results,utils}
touch secaudit-core/requirements.txt
touch secaudit-core/main.py
touch secaudit-core/modules/{__init__.py,audit_runner.py,bash_executor.py}
touch secaudit-core/utils/logger.py
touch secaudit-core/profiles/baseline.yml
touch secaudit-core/results/.gitkeep
touch secaudit-core/README.md
touch secaudit-core/.gitignore

echo "pyyaml" > secaudit-core/requirements.txt

echo "[+] Project create."
