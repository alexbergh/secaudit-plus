.PHONY: venv deps lint test build install clean

venv:
	python3 -m venv venv

deps:
	. venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt && pip install build flake8 pytest

lint:
	. venv/bin/activate && flake8 modules secaudit utils tests --max-line-length=120 --exclude __init__.py

test:
	. venv/bin/activate && pytest -q

build:
	. venv/bin/activate && python -m build

install:
	. venv/bin/activate && pip install .

clean:
	rm -rf dist build *.egg-info .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
