# DockView — Development Guide

## Setup

```bash
git clone https://github.com/0xSemantic/dockview.git
cd dockview

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8080
```

## Project conventions

- **Python 3.12+**, type hints throughout
- **Async everywhere** — all DB operations use async drivers
- **Pydantic models** for all API inputs and outputs
- **No ORM** — raw driver queries for full control and performance

## Adding a database adapter

1. Create `app/adapters/mydb.py` with `@register(DatabaseType.MYDB)` decorator
2. Add `DatabaseType.MYDB` to `app/models.py` enum
3. Add image detection pattern to `app/services/docker_inspector.py` `IMAGE_PATTERNS`
4. Import adapter in `app/adapters/registry.py`

## Running tests

```bash
pytest tests/ -v
```

Integration tests require Docker and running database containers (the compose file sets these up).

## Code style

```bash
# Format
ruff format .

# Lint
ruff check .

# Type check
mypy app/
```

## Making a PR

1. Fork and create a feature branch
2. Add tests for new functionality
3. Ensure `ruff` and `mypy` pass
4. Submit PR with a clear description of what and why
