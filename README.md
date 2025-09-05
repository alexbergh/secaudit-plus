> SecAudit-core

**SecAudit-core** —  CLI-инструмент для аудита безопасности Linux-систем по профилям ФСТЭК, СТЭК, NIST и ISO.  
Ориентирован на автоматизацию, масштабируемость и гибкость (через YAML).

- Поддержка YAML-профилей
- Аудит SSH, PAM, SUDO, root-настроек
- JSON-отчёт с PASS/FAIL
- Расширяемая архитектура

```bash
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
# Запуск аудита с ошибкой при UNDEF
python3 main.py audit --fail-on-undef

---

##  Тест

Для проверки логики assert'ов (`exact`, `contains`, `regexp`, `not_contains`) реализованы модульные юнит-тесты на `pytest`.

### Установка

```bash
pip install -r requirements.txt

## Установка из исходников

```bash
python3 -m venv venv
source venv/bin/activate
pip install .

