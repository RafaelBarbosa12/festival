# Deauville Festival du Rire 2027

Programme of the first edition (10–13 June 2027): venues, artists, solo
shows, lineups and workshops. Organisers schedule through an HTTP API and a
small admin site; the public site only reads.

## Install

Python 3.12 and [uv](https://docs.astral.sh/uv/). Then:

```bash
uv sync
```

## Run

Command line (data file: `data/festival.json`):

```bash
uv run deauville
uv run deauville venues
uv run deauville programme 2027-06-11
uv run deauville artist lea-fontaine
uv run deauville now 2027-06-11T21:00
uv run deauville --data data/festival.json programme 2027-06-11
```

Website and admin (http://127.0.0.1:8000/ and `/admin/`):

```bash
uv run deauville serve
```

Another port: `uv run deauville --port 8001 serve`.

## Tests

```bash
uv run pytest
uv run ruff format .
uv run ruff check .
uv build
```

API tests copy the JSON into a temp folder. `data/festival.json` is not
written by pytest.

## Structure

| Where | Why |
| ----- | --- |
| `src/deauville/models.py` | Venue, Artist, `Performance` (abstract), SoloShow, Lineup, Workshop. Kind-specific rules live on the subclass. |
| `src/deauville/festival.py` | The 2027 edition. Schedule rules (duration, festival day, 30-minute gap for a venue or an artist). The only way to mutate `_performances` / `_artists`. |
| `src/deauville/errors.py` | `FestivalError` and three subclasses: not found, conflict, invalid. |
| `src/deauville/storage.py` | `Storage.load` / `save`. JSON on disk, or memory for tests. The festival does not open a file. |
| `src/deauville/api.py` | `create_app(storage)`: routes of `API.md`, one exception handler, static files. |
| `src/deauville/cli.py` | `uv run deauville …` and `serve`. |
| `web/public/` | Public site. |
| `web/admin/` | Organisers: add, move, cancel, register, add an artist. |
| `data/festival.json` | The edition. |
| `API.md` | HTTP contract. |

A request such as `POST /api/performances` becomes a `SoloShow` / `Lineup` /
`Workshop` (`build_performance`), then `Festival.add` (or `replace`). If a
rule fails, a `FestivalError` is raised. The API never writes `try` in a
route: `@app.exception_handler(FestivalError)` maps the type to 404, 409 or
422.

A database would replace `JsonStorage` only. Festival classes stay the same.

## Done

- Command line of steps 00–05, night shows on the right festival day.
- Public site and admin, whole `API.md`, tests, package, `uv build`.
- Encapsulation: appending on `festival.performances` does not change the
  schedule.

## Not done / known bugs

- No SQLite storage (optional extension of step 13).
- The admin is forms, not a full editor: you type slugs and ids.
- `GET /api/now` without `?at=` uses the real clock, so outside June 2027
  the homepage shows an empty “on stage now”.
- Photos of artists are empty strings in the data file.
