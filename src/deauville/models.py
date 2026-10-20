"""Venues, artists, and the three kinds of performances."""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from deauville.errors import ConflictError, InvalidError

DAY_CHANGE = timedelta(hours=6)
GAP = timedelta(minutes=30)


def slugify(text: str) -> str:
    """Théâtre des Planches -> theatre-des-planches."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = decomposed.encode("ascii", "ignore").decode("ascii")
    result = ""
    for char in plain.lower():
        if char.isalnum():
            result += char
        elif not result.endswith("-"):
            result += "-"
    return result.strip("-")


@dataclass
class Venue:
    """A room of the festival. The slug is computed from the name."""

    name: str
    capacity: int
    address: str
    slug: str = field(init=False)

    def __post_init__(self) -> None:
        self.slug = slugify(self.name)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }


@dataclass
class Artist:
    """Someone who can go on stage. Two artists are equal if their slug is."""

    name: str
    bio: str = ""
    photo_url: str = ""
    slug: str = field(init=False)

    def __post_init__(self) -> None:
        self.slug = slugify(self.name)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artist):
            return NotImplemented
        return self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)


class Performance(ABC):
    """What every show shares. Performance itself cannot be created."""

    kind = "performance"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        return (self.start - DAY_CHANGE).date()

    @property
    def id(self) -> str:
        return f"{self.venue.slug}-{self.start:%Y-%m-%d-%H%M}"

    @abstractmethod
    def people_on_stage(self) -> list[Artist]:
        """Who occupies a slot: soloist, host+acts, or teacher."""

    @abstractmethod
    def summary(self) -> str:
        """One line for the website card."""

    @abstractmethod
    def role_of(self, artist: Artist) -> str | None:
        """solo, host, act or teacher — or None."""

    @abstractmethod
    def kind_view(self) -> dict:
        """Fields that only this kind sends to the API."""

    @abstractmethod
    def kind_row(self) -> dict:
        """Fields that only this kind writes back to the JSON file."""

    def involves(self, artist: Artist) -> bool:
        return artist in self.people_on_stage()

    def is_running(self, at: datetime) -> bool:
        return self.start <= at < self.end

    def too_close(self, other: Performance) -> bool:
        return self.start < other.end + GAP and other.start < self.end + GAP

    def __lt__(self, other: Performance) -> bool:
        return (self.start, self.venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        return (
            f"{self.start:%H:%M}-{self.end:%H:%M} | "
            f"{self.venue.name} | {self.title} ({self.kind})"
        )

    def to_view(self) -> dict:
        view = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "venue_name": self.venue.name,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary(),
            "capacity": self.venue.capacity,
            "artists": [
                {"slug": person.slug, "name": person.name}
                for person in self.people_on_stage()
            ],
        }
        view.update(self.kind_view())
        return view

    def to_row(self) -> dict:
        row = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        row.update(self.kind_row())
        return row


class SoloShow(Performance):
    """One artist, optional minimum age 0–18."""

    kind = "solo"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        artist: Artist,
        min_age: int = 0,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        if not 0 <= min_age <= 18:
            raise InvalidError(f"Minimum age must be from 0 to 18, not {min_age}.")
        self.artist = artist
        self.min_age = min_age

    @classmethod
    def from_row(cls, row: dict, venue: Venue, artists: dict[str, Artist]) -> SoloShow:
        return cls(
            title=row["title"],
            venue=venue,
            start=datetime.fromisoformat(row["start"]),
            duration_minutes=row["duration_minutes"],
            artist=artists[row["artist"]],
            min_age=row.get("min_age", 0),
            description=row.get("description", ""),
        )

    def people_on_stage(self) -> list[Artist]:
        return [self.artist]

    def summary(self) -> str:
        return self.artist.name

    def role_of(self, artist: Artist) -> str | None:
        if artist == self.artist:
            return "solo"
        return None

    def kind_view(self) -> dict:
        return {"artist": self.artist.slug, "min_age": self.min_age}

    def kind_row(self) -> dict:
        return {"artist": self.artist.slug, "min_age": self.min_age}


class Lineup(Performance):
    """A host and at least two distinct acts. Duration: 10 min/act + 3 between."""

    kind = "lineup"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        host: Artist,
        acts: list[Artist],
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self.host = host
        self._acts = list(acts)
        if len(self._acts) < 2:
            raise InvalidError("A lineup needs at least two acts.")
        if len(self._acts) != len(set(self._acts)):
            raise InvalidError("Each act can appear only once.")
        if self.host in self._acts:
            raise InvalidError("The host cannot also be an act.")
        needed = 10 * len(self._acts) + 3 * (len(self._acts) - 1)
        if self.duration_minutes < needed:
            raise InvalidError(
                f"A lineup of {len(self._acts)} acts needs at least {needed} minutes."
            )

    @property
    def acts(self) -> list[Artist]:
        return list(self._acts)

    @classmethod
    def from_row(cls, row: dict, venue: Venue, artists: dict[str, Artist]) -> Lineup:
        return cls(
            title=row["title"],
            venue=venue,
            start=datetime.fromisoformat(row["start"]),
            duration_minutes=row["duration_minutes"],
            host=artists[row["host"]],
            acts=[artists[slug] for slug in row["acts"]],
            description=row.get("description", ""),
        )

    def people_on_stage(self) -> list[Artist]:
        return [self.host, *self._acts]

    def summary(self) -> str:
        names = ", ".join(act.name for act in self._acts)
        return f"hosted by {self.host.name}, with {names}"

    def role_of(self, artist: Artist) -> str | None:
        if artist == self.host:
            return "host"
        if artist in self._acts:
            return "act"
        return None

    def kind_view(self) -> dict:
        return {"host": self.host.slug, "acts": [act.slug for act in self._acts]}

    def kind_row(self) -> dict:
        return {"host": self.host.slug, "acts": [act.slug for act in self._acts]}


class Workshop(Performance):
    """A teacher and places = min(max_participants, venue seats)."""

    kind = "workshop"

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        teacher: Artist,
        max_participants: int,
        participants: list[str] | None = None,
        description: str = "",
    ) -> None:
        super().__init__(title, venue, start, duration_minutes, description)
        self.teacher = teacher
        self.max_participants = max_participants
        self._participants = list(participants or [])
        if self.places < 1:
            raise InvalidError("A workshop needs at least one place.")

    @property
    def participants(self) -> list[str]:
        return list(self._participants)

    @property
    def places(self) -> int:
        return min(self.max_participants, self.venue.capacity)

    @property
    def places_left(self) -> int:
        return self.places - len(self._participants)

    def register(self, name: str) -> None:
        cleaned = name.strip()
        if cleaned == "":
            raise InvalidError("A participant needs a name.")
        if cleaned in self._participants:
            raise ConflictError(f"{cleaned} is already registered.")
        if self.places_left < 1:
            raise ConflictError(f"{self.title} is full.")
        self._participants.append(cleaned)

    @classmethod
    def from_row(cls, row: dict, venue: Venue, artists: dict[str, Artist]) -> Workshop:
        return cls(
            title=row["title"],
            venue=venue,
            start=datetime.fromisoformat(row["start"]),
            duration_minutes=row["duration_minutes"],
            teacher=artists[row["teacher"]],
            max_participants=row["max_participants"],
            participants=list(row.get("participants", [])),
            description=row.get("description", ""),
        )

    def people_on_stage(self) -> list[Artist]:
        return [self.teacher]

    def summary(self) -> str:
        taken = len(self._participants)
        return f"with {self.teacher.name}, {taken}/{self.places} places taken"

    def role_of(self, artist: Artist) -> str | None:
        if artist == self.teacher:
            return "teacher"
        return None

    def kind_view(self) -> dict:
        return {
            "teacher": self.teacher.slug,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
            "places_left": self.places_left,
        }

    def kind_row(self) -> dict:
        return {
            "teacher": self.teacher.slug,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
        }


KINDS = {"solo": SoloShow, "lineup": Lineup, "workshop": Workshop}


def performance_from_row(
    row: dict, venue: Venue, artists: dict[str, Artist]
) -> Performance:
    if row["kind"] not in KINDS:
        raise InvalidError(f"Unknown kind {row['kind']!r}.")
    return KINDS[row["kind"]].from_row(row, venue, artists)
