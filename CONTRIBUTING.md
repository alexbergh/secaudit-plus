# Contributing to SecAudit+

Спасибо за интерес к проекту SecAudit+!

## Как внести вклад

### Сообщение об ошибках

Перед созданием issue проверьте, что проблема еще не была зарегистрирована:

1. Используйте GitHub search для поиска существующих issues
2. Если проблема новая, создайте issue с подробным описанием:
   - Версия SecAudit+
   - Версия Python
   - ОС и версия
   - Шаги для воспроизведения
   - Ожидаемое и фактическое поведение
   - Логи и скриншоты (если применимо)

### Предложение улучшений

Для новых функций или улучшений:

1. Создайте issue с тегом `enhancement`
2. Опишите проблему, которую решает предложение
3. Предложите решение
4. Обсудите с maintainers перед началом работы

### Pull Requests

#### Процесс

1. **Fork** репозитория
2. **Clone** вашего fork
3. Создайте **feature branch**: `git checkout -b feature/amazing-feature`
4. Внесите изменения
5. **Commit** с понятным сообщением
6. **Push** в ваш fork
7. Создайте **Pull Request**

#### Требования к PR

- ✅ Код соответствует стилю проекта (flake8, mypy)
- ✅ Добавлены тесты для новой функциональности
- ✅ Все тесты проходят (`pytest`)
- ✅ Документация обновлена
- ✅ CHANGELOG.md обновлен (если применимо)
- ✅ Commit messages информативные

#### Стиль кода

```bash
# Установите pre-commit hooks
pip install pre-commit
pre-commit install

# Проверка кода
flake8 modules secaudit utils tests
mypy modules secaudit utils tests
yamllint profiles

# Запуск тестов
pytest -v --cov
```

#### Commit Messages

Используйте conventional commits:

```
type(scope): subject

body

footer
```

**Types:**
- `feat`: новая функция
- `fix`: исправление бага
- `docs`: изменения в документации
- `style`: форматирование кода
- `refactor`: рефакторинг
- `test`: добавление тестов
- `chore`: обновление зависимостей, CI и т.д.

**Примеры:**
```
feat(profiles): add PostgreSQL audit checks
fix(cli): handle missing profile gracefully
docs(readme): update installation instructions
```

### Разработка

#### Настройка окружения

```bash
# Clone репозитория
git clone https://github.com/alexbergh/secaudit-core.git
cd secaudit-core

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate

# Установка зависимостей
pip install -e .
pip install -r requirements.txt

# Установка pre-commit hooks
pre-commit install
```

#### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=modules --cov=secaudit --cov-report=html

# Конкретный тест
pytest tests/test_cli.py -v

# С маркерами
pytest -m "not slow"
```

#### Локальная проверка CI

```bash
# Линтеры
flake8 modules secaudit utils tests --max-line-length=120
mypy modules secaudit utils tests --ignore-missing-imports
yamllint profiles .github/workflows

# Security сканирование
bandit -r modules secaudit utils
safety check

# Сборка пакета
python -m build
```

### Добавление профилей аудита

При добавлении новых проверок в профили:

1. **Структура проверки:**
```yaml
- id: "unique_check_id"
  name: "Понятное имя проверки"
  module: "system|network|services|..."
  command: "команда для выполнения"
  expect: "ожидаемый результат"
  assert_type: "exact|contains|regexp|..."
  severity: "low|medium|high"
  tags:
    fstek: "requirement_id"
    cis: "benchmark_id"
```

2. **Валидация:**
```bash
secaudit validate --profile profiles/your-profile.yml --strict
```

3. **Тестирование:**
```bash
secaudit audit --profile profiles/your-profile.yml --level baseline
```

4. **Документация:**
   - Добавьте описание в профиль
   - Обновите README.md
   - Добавьте примеры использования

### Код ревью

Все PR проходят код ревью. Ожидайте:

- Проверку соответствия стилю
- Вопросы о дизайне решения
- Предложения по улучшению
- Запросы на дополнительные тесты

Будьте готовы к итерациям и обсуждениям.

### Лицензия

Внося вклад, вы соглашаетесь с тем, что ваш код будет распространяться под лицензией Apache License 2.0.

### Вопросы?

- GitHub Discussions для общих вопросов
- GitHub Issues для багов и feature requests
- Email для приватных вопросов

## Благодарности

Спасибо всем контрибьюторам! Ваш вклад делает SecAudit+ лучше.
