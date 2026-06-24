# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-page expenses tracker. Stdlib-only Python backend (`app.py`) serving a single HTML/CSS/JS frontend (`templates/index.html`). No build system, no framework, no third-party dependencies. UI text is in Portuguese.

## Running

```bash
python3 app.py
```

Serves on `http://0.0.0.0:8020`. No virtualenv or package manager needed — `app.py` only uses Python stdlib (`http.server`, `json`, `csv`).

## Architecture

`app.py` is a `BaseHTTPRequestHandler` subclass (`Handler`) on `ThreadingHTTPServer`, hand-routing JSON REST endpoints via `do_GET`/`do_POST`/`do_DELETE` (no Flask/Django). Data is persisted as flat JSON files, not a database:

- `expenses.json` — array of expense objects (`id`, `title`, `description`, `date`, `time`, `amount`, `categories[]`). `id` is a millisecond timestamp string.
- `categories.json` — flat array of category name strings.

Both files are read/written in full on every operation via `load_json`/`save_json` (no partial updates, no locking). If a file doesn't exist it's created with a default (`DEFAULT_CATEGORIES = ["Casa", "Obras"]` for categories, `[]` for expenses).

### API routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | serves `templates/index.html` |
| GET | `/api/expenses?category=` | list expenses, optional category filter, sorted by date+time desc |
| POST | `/api/expenses` | add expense (requires `title`, numeric `amount`) |
| DELETE | `/api/expenses/<id>` | remove expense by id |
| GET | `/api/categories` | list categories |
| POST | `/api/categories` | add category (no-op if name already exists) |
| GET | `/api/export/csv?category=` | download CSV (UTF-8 BOM, same filtering/sorting as list) |

All error responses are JSON `{"error": "..."}` with Portuguese messages.

### Frontend

`templates/index.html` is a single self-contained file: inline `<style>` (dark theme, CSS custom properties for colors) and inline `<script>` that calls the `/api/*` endpoints with `fetch`. No separate JS/CSS files, no template inheritance.

## Conventions

- Keep `app.py` dependency-free (stdlib only) — this is intentional, not an oversight.
- Category chips use multi-select toggling against the `categories[]` array on each expense.
- When adding fields to expenses, update: the `handle_add_expense` schema, the CSV header/row in `handle_export_csv`, and the corresponding form/render logic in `index.html`.
