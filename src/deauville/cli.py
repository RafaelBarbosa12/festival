"""Command line: uv run deauville programme 2027-06-11, uv run deauville serve."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import uvicorn

from deauville.api import create_app
from deauville.errors import FestivalError, InvalidError
from deauville.festival import Festival
from deauville.paths import project_root
from deauville.storage import JsonStorage, Storage

WEEKDAYS_LONG = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
WEEKDAYS_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_long_day(day: date) -> str:
    """Friday 11 June."""
    return f"{WEEKDAYS_LONG[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def format_short_day(day: date) -> str:
    """Fri 11."""
    return f"{WEEKDAYS_SHORT[day.weekday()]} {day.day}"


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a day, use YYYY-MM-DD.") from None


def parse_moment(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise InvalidError(
            f"{text!r} is not a date and time, use YYYY-MM-DDTHH:MM."
        ) from None


def parse_minutes(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise InvalidError(f"{text!r} is not a number of minutes.") from None


def print_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def print_venues(festival: Festival) -> None:
    total = 0
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
        total += venue.capacity
    print(f"Total: {total} seats")


def print_programme(festival: Festival, day_text: str) -> None:
    day = parse_day(day_text)
    print(f"Programme for {format_long_day(day)}:")
    for performance in festival.programme(day=day):
        print(performance)


def print_artist(festival: Festival, slug: str) -> None:
    artist = festival.require_artist(slug)
    print(artist.name)
    for performance in festival.performances_of(artist):
        role = performance.role_of(artist)
        print(
            f"{format_short_day(performance.festival_day)} "
            f"{performance.start:%H:%M}-{performance.end:%H:%M} | "
            f"{performance.venue.name} | {performance.title} ({role})"
        )


def print_now(festival: Festival, moment_text: str) -> None:
    at = parse_moment(moment_text)
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    for performance in festival.now_playing(at):
        print(
            f"- {performance.title} at {performance.venue.name}, "
            f"until {performance.end:%H:%M}"
        )
    print("Up next:")
    for performance in festival.up_next(at):
        print(f"- {performance}")


def command_add(festival: Festival, storage: Storage) -> None:
    title = input("Title: ").strip()
    artist_slug = input("Artist (slug): ").strip()
    venue_slug = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    duration_minutes = parse_minutes(input("Duration (minutes): ").strip())
    new = festival.add_solo(title, artist_slug, venue_slug, start, duration_minutes)
    storage.save(festival)
    print(f"Added: {new.id}")


def command_cancel(festival: Festival, storage: Storage, performance_id: str) -> None:
    removed = festival.cancel(performance_id)
    storage.save(festival)
    print(f"Cancelled: {removed.title}")


def print_usage() -> None:
    print(
        "uv run deauville [--data FILE] [venues|programme DAY|artist SLUG|"
        "now MOMENT|add|cancel ID|serve]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="deauville", add_help=True)
    parser.add_argument(
        "--data",
        default=str(project_root() / "data" / "festival.json"),
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("command", nargs="?", default="")
    parser.add_argument("values", nargs="*")
    parsed = parser.parse_args()
    storage = JsonStorage(Path(parsed.data))

    try:
        if parsed.command == "serve":
            uvicorn.run(
                create_app(storage),
                host="127.0.0.1",
                port=parsed.port,
            )
            return

        festival = storage.load()
        command = parsed.command
        values = parsed.values
        if command == "":
            print_summary(festival)
        elif command == "venues":
            print_venues(festival)
        elif command == "programme" and len(values) == 1:
            print_programme(festival, values[0])
        elif command == "artist" and len(values) == 1:
            print_artist(festival, values[0])
        elif command == "now" and len(values) == 1:
            print_now(festival, values[0])
        elif command == "add" and values == []:
            command_add(festival, storage)
        elif command == "cancel" and len(values) == 1:
            command_cancel(festival, storage, values[0])
        else:
            print_usage()
    except FestivalError as error:
        print(f"Error: {error}")
        sys.exit(1)
