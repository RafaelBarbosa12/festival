"""The festival holds the collections and the rules of the brief."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from deauville.errors import ConflictError, FestivalError, InvalidError, NotFoundError
from deauville.models import (
    Artist,
    Lineup,
    Performance,
    SoloShow,
    Venue,
    Workshop,
    performance_from_row,
)


class Festival:
    """One edition: days, venues, artists, schedule. Mutations go through methods."""

    def __init__(
        self,
        name: str,
        first_day: date,
        last_day: date,
        venues: list[Venue],
        artists: list[Artist],
        performances: list[Performance],
    ) -> None:
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        self._venues = venues
        self._artists = artists
        self._performances = performances

    @property
    def venues(self) -> list[Venue]:
        return list(self._venues)

    @property
    def artists(self) -> list[Artist]:
        return list(self._artists)

    @property
    def performances(self) -> list[Performance]:
        return list(self._performances)

    @property
    def days(self) -> list[date]:
        days = []
        day = self.first_day
        while day <= self.last_day:
            days.append(day)
            day += timedelta(days=1)
        return days

    def venue_by_slug(self, slug: str) -> Venue | None:
        for venue in self._venues:
            if venue.slug == slug:
                return venue
        return None

    def artist_by_slug(self, slug: str) -> Artist | None:
        for artist in self._artists:
            if artist.slug == slug:
                return artist
        return None

    def require_venue(self, slug: str) -> Venue:
        venue = self.venue_by_slug(slug)
        if venue is None:
            raise NotFoundError(f"No venue {slug!r}.")
        return venue

    def require_artist(self, slug: str) -> Artist:
        artist = self.artist_by_slug(slug)
        if artist is None:
            raise NotFoundError(f"No artist {slug!r}.")
        return artist

    def require_performance(self, performance_id: str) -> Performance:
        performance = self.performance_by_id(performance_id)
        if performance is None:
            raise NotFoundError(f"No performance {performance_id!r}.")
        return performance

    def performance_by_id(self, performance_id: str) -> Performance | None:
        for performance in self._performances:
            if performance.id == performance_id:
                return performance
        return None

    def programme(
        self, day: date | None = None, venue_slug: str | None = None
    ) -> list[Performance]:
        result = []
        for performance in self._performances:
            if day is not None and performance.festival_day != day:
                continue
            if venue_slug is not None and performance.venue.slug != venue_slug:
                continue
            result.append(performance)
        return sorted(result)

    def performances_of(self, artist: Artist) -> list[Performance]:
        result = []
        for performance in self._performances:
            if performance.involves(artist):
                result.append(performance)
        return sorted(result)

    def now_playing(self, at: datetime) -> list[Performance]:
        result = []
        for performance in self._performances:
            if performance.is_running(at):
                result.append(performance)
        return sorted(result)

    def up_next(self, at: datetime, limit: int = 3) -> list[Performance]:
        upcoming = []
        for performance in self._performances:
            if performance.start > at:
                upcoming.append(performance)
        return sorted(upcoming)[:limit]

    def now_view(self, at: datetime) -> dict:
        return {
            "at": at.isoformat(timespec="minutes"),
            "now_playing": [item.to_view() for item in self.now_playing(at)],
            "up_next": [item.to_view() for item in self.up_next(at)],
        }

    def to_view(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "days": [day.isoformat() for day in self.days],
        }

    def to_data(self) -> dict:
        """JSON shape of the data file."""
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [
                {
                    "name": venue.name,
                    "capacity": venue.capacity,
                    "address": venue.address,
                }
                for venue in self._venues
            ],
            "artists": [
                {
                    "name": artist.name,
                    "bio": artist.bio,
                    "photo_url": artist.photo_url,
                }
                for artist in self._artists
            ],
            "performances": [item.to_row() for item in self._performances],
        }

    def check(self, new: Performance) -> None:
        if not 1 <= new.duration_minutes <= 360:
            raise InvalidError(
                f"Duration must be from 1 to 360 minutes, not {new.duration_minutes}."
            )
        if not self.first_day <= new.festival_day <= self.last_day:
            raise ConflictError(
                f"{new.festival_day.isoformat()} is not a day of the festival."
            )
        for other in self._performances:
            if other.venue.slug == new.venue.slug and new.too_close(other):
                raise ConflictError(
                    f"{new.venue.name} is busy with {other.title} "
                    f"({other.start:%Y-%m-%d %H:%M}-{other.end:%H:%M}). "
                    "Leave 30 minutes between two shows."
                )
        for person in new.people_on_stage():
            for other in self._performances:
                if other.involves(person) and new.too_close(other):
                    raise ConflictError(f"{person.name} is on stage in {other.title}.")

    def add(self, new: Performance) -> None:
        self.check(new)
        self._performances.append(new)

    def add_solo(
        self,
        title: str,
        artist_slug: str,
        venue_slug: str,
        start: datetime,
        duration_minutes: int,
    ) -> Performance:
        new = SoloShow(
            title=title,
            venue=self.require_venue(venue_slug),
            start=start,
            duration_minutes=duration_minutes,
            artist=self.require_artist(artist_slug),
            min_age=0,
        )
        self.add(new)
        return new

    def build_performance(self, body: dict) -> Performance:
        """Turn an API/admin body into a SoloShow, Lineup or Workshop."""
        title = body.get("title")
        venue_slug = body.get("venue")
        start = body.get("start")
        duration_minutes = body.get("duration_minutes")
        if not title:
            raise InvalidError("A performance needs a title.")
        if not venue_slug:
            raise InvalidError("A performance needs a venue.")
        if start is None:
            raise InvalidError("A performance needs a start.")
        if duration_minutes is None:
            raise InvalidError("A performance needs a duration.")
        venue = self.require_venue(venue_slug)
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        description = body.get("description") or ""

        def solo() -> Performance:
            if not body.get("artist"):
                raise InvalidError("A solo show needs an artist.")
            return SoloShow(
                title,
                venue,
                start,
                duration_minutes,
                self.require_artist(body["artist"]),
                body.get("min_age", 0),
                description,
            )

        def lineup() -> Performance:
            if not body.get("host"):
                raise InvalidError("A lineup needs a host.")
            return Lineup(
                title,
                venue,
                start,
                duration_minutes,
                self.require_artist(body["host"]),
                [self.require_artist(slug) for slug in body.get("acts") or []],
                description,
            )

        def workshop() -> Performance:
            if not body.get("teacher"):
                raise InvalidError("A workshop needs a teacher.")
            if body.get("max_participants") is None:
                raise InvalidError("A workshop needs max_participants.")
            return Workshop(
                title,
                venue,
                start,
                duration_minutes,
                self.require_artist(body["teacher"]),
                body["max_participants"],
                body.get("participants") or [],
                description,
            )

        builders = {"solo": solo, "lineup": lineup, "workshop": workshop}
        kind = body.get("kind")
        if kind not in builders:
            raise InvalidError(f"Unknown kind {kind!r}.")
        return builders[kind]()

    def replace(self, performance_id: str, new: Performance) -> Performance:
        old = self.require_performance(performance_id)
        index = self._performances.index(old)
        self._performances.pop(index)
        try:
            self.check(new)
        except FestivalError:
            self._performances.insert(index, old)
            raise
        self._performances.append(new)
        return new

    def cancel(self, performance_id: str) -> Performance:
        performance = self.require_performance(performance_id)
        self._performances.remove(performance)
        return performance

    def register(self, performance_id: str, name: str) -> Workshop:
        performance = self.require_performance(performance_id)
        if not isinstance(performance, Workshop):
            raise InvalidError(f"{performance.title} is not a workshop.")
        performance.register(name)
        return performance

    def add_artist(self, name: str, bio: str = "", photo_url: str = "") -> Artist:
        artist = Artist(name, bio, photo_url)
        if self.artist_by_slug(artist.slug) is not None:
            raise ConflictError(f"Artist {artist.slug!r} already exists.")
        self._artists.append(artist)
        return artist


def festival_from_data(data: dict) -> Festival:
    venues = [
        Venue(row["name"], row["capacity"], row["address"]) for row in data["venues"]
    ]
    artists = [
        Artist(row["name"], row.get("bio", ""), row.get("photo_url", ""))
        for row in data["artists"]
    ]
    venues_by_slug = {venue.slug: venue for venue in venues}
    artists_by_slug = {artist.slug: artist for artist in artists}
    performances = [
        performance_from_row(row, venues_by_slug[row["venue"]], artists_by_slug)
        for row in data["performances"]
    ]
    return Festival(
        name=data["name"],
        first_day=date.fromisoformat(data["first_day"]),
        last_day=date.fromisoformat(data["last_day"]),
        venues=venues,
        artists=artists,
        performances=performances,
    )
