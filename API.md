# API — Deauville Festival du Rire

The website and the admin talk to the program only through these routes.
Field names are a contract.

## Objects

**Festival** `{name, first_day, last_day, days}`

**Venue** `{slug, name, capacity, address}`

**Artist** `{slug, name, bio, photo_url}` — on `GET /api/artists/{slug}`, also `performances`.

**Performance** (common) `{id, kind, title, venue, venue_name, start, end, duration_minutes, festival_day, description, summary, capacity, artists}` where `artists` is `[{slug, name}, ...]`.

- solo also has `artist`, `min_age`
- lineup also has `host`, `acts`
- workshop also has `teacher`, `max_participants`, `participants`, `places_left`

`start` / `end` use `YYYY-MM-DDTHH:MM`. `id` is `{venue}-{YYYY-MM-DD}-{HHMM}`.

## Read

| Method | Path | Query | Success |
| ------ | ---- | ----- | ------- |
| GET | `/api/festival` | | 200 festival |
| GET | `/api/venues` | | 200 list, file order |
| GET | `/api/venues/{slug}` | | 200 one venue |
| GET | `/api/artists` | | 200 list, sorted by slug |
| GET | `/api/artists/{slug}` | | 200 artist + performances |
| GET | `/api/programme` | `day` (date), `venue` (slug) | 200 list |
| GET | `/api/performances/{id}` | | 200 one performance |
| GET | `/api/now` | `at` (datetime); default now | 200 `{at, now_playing, up_next}` (`up_next` ≤ 3) |

## Write (admin)

| Method | Path | Body | Success |
| ------ | ---- | ---- | ------- |
| POST | `/api/performances` | performance in | 201 view |
| PUT | `/api/performances/{id}` | performance in | 200 view (id may change) |
| DELETE | `/api/performances/{id}` | | 204 empty |
| POST | `/api/performances/{id}/participants` | `{name}` | 200 workshop view |
| POST | `/api/artists` | `{name, bio?, photo_url?}` | 201 artist view |

Performance in: `{kind, title, venue, start, duration_minutes, description?}` plus the fields of the kind (`artist`/`min_age`, `host`/`acts`, `teacher`/`max_participants`).

A refused PUT leaves the schedule unchanged.

## Errors

`{"detail": "a sentence"}`

| Situation | Status |
| --------- | ------ |
| unknown venue, artist, performance | 404 |
| venue busy, artist busy, workshop full, name already registered, artist slug already exists | 409 |
| invalid duration, day, kind rules, missing/invalid body | 422 |
| `?day=June 11` (not ISO) | 422 (FastAPI) |
| data file cannot be written | 500 |
