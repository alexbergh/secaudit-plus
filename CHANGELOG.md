# История изменений

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Добавлено
- GitHub Actions workflows для CI/CD
- Конфигурация Dependabot для автоматического обновления зависимостей
- Поддержка Docker с Dockerfile и docker-compose.yml
- SECURITY.md с политикой безопасности и процессом раскрытия уязвимостей
- Анализ CodeQL для сканирования безопасности
- Интеграция Semgrep для SAST
- Gitleaks и TruffleHog для обнаружения секретов
- Bandit security linter в CI
- Отчеты о покрытии тестами с pytest-cov
- CONTRIBUTING.md с руководством для контрибьюторов
- Конфигурация pre-commit hooks
- Makefile для общих задач

### Изменено
- Перемещены workflows из `workflows/` в `.github/workflows/`
- Расширен CI pipeline сканированием безопасности
- Улучшены отчеты о покрытии тестами

### Безопасность
- Добавлены множественные инструменты сканирования безопасности
- Реализовано обнаружение секретов
- Добавлен SARIF вывод для находок безопасности

## [1.0.0] - 2025-01-28

### Добавлено
- Первый релиз SecAudit+
- YAML-профили аудита с наследованием
- Поддержка требований ФСТЭК, CIS Benchmarks
- Шаблоны Jinja2 для отчетов
- Форматы отчетов: JSON, Markdown, HTML, SARIF, JUnit
- Экспорт в Prometheus и Elasticsearch
- Параллельное выполнение проверок
- Подстановка переменных с уровнями критичности
- Сбор доказательств
- Валидация профилей с JSON Schema
- CLI с множественными командами (audit, validate, compare и др.)
- Комплексный набор тестов
- Документация и руководство пользователя

### Поддерживаемые платформы
- Linux (Debian, Ubuntu, CentOS, ALT, Astra, RED OS)
- Python 3.10+

[Unreleased]: https://github.com/alexbergh/secaudit-core/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/alexbergh/secaudit-core/releases/tag/v1.0.0
