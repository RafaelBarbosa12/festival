"""HTTP API for the website and the admin.

uv run deauville serve
"""

from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from deauville.errors import (
    ConflictError,
    FestivalError,
    InvalidError,
    NotFoundError,
)
from deauville.festival import Festival
from deauville.storage import JsonStorage, Storage

STATUS = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidError: 422,
}


class PerformanceIn(BaseModel):
    kind: str
    title: str
    venue: str
    start: datetime
    duration_minutes: int
    description: str = ""
    artist: str | None = None
    min_age: int = 0
    host: str | None = None
    acts: list[str] = Field(default_factory=list)
    teacher: str | None = None
    max_participants: int | None = None
    participants: list[str] = Field(default_factory=list)


class ParticipantIn(BaseModel):
    name: str


class ArtistIn(BaseModel):
    name: str
    bio: str = ""
    photo_url: str = ""


def create_app(storage: Storage) -> FastAPI:
    """A new application around one storage. Tests pass a temp file."""
    app = FastAPI(title="Deauville Festival du Rire")

    def festival() -> Festival:
        return storage.load()

    def persist(fest: Festival) -> None:
        try:
            storage.save(fest)
        except OSError as error:
            raise HTTPException(
                status_code=500,
                detail=f"Could not write the data file: {error}",
            ) from error

    @app.exception_handler(FestivalError)
    def festival_error(_request: Request, error: FestivalError) -> JSONResponse:
        status = STATUS.get(type(error), 400)
        return JSONResponse(status_code=status, content={"detail": str(error)})

    @app.get("/api/festival")
    def read_festival() -> dict:
        return festival().to_view()

    @app.get("/api/venues")
    def list_venues() -> list[dict]:
        return [venue.to_view() for venue in festival().venues]

    @app.get("/api/venues/{slug}")
    def read_venue(slug: str) -> dict:
        return festival().require_venue(slug).to_view()

    @app.get("/api/artists")
    def list_artists() -> list[dict]:
        artists = [artist.to_view() for artist in festival().artists]
        artists.sort(key=lambda item: item["slug"])
        return artists

    @app.get("/api/artists/{slug}")
    def read_artist(slug: str) -> dict:
        fest = festival()
        artist = fest.require_artist(slug)
        view = artist.to_view()
        view["performances"] = [item.to_view() for item in fest.performances_of(artist)]
        return view

    @app.get("/api/programme")
    def list_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
        fest = festival()
        if venue is not None:
            fest.require_venue(venue)
        return [item.to_view() for item in fest.programme(day=day, venue_slug=venue)]

    @app.get("/api/now")
    def read_now(at: datetime | None = None) -> dict:
        moment = at if at is not None else datetime.now()
        return festival().now_view(moment)

    @app.get("/api/performances/{performance_id}")
    def read_performance(performance_id: str) -> dict:
        return festival().require_performance(performance_id).to_view()

    @app.post("/api/performances", status_code=201)
    def create_performance(body: PerformanceIn) -> dict:
        fest = festival()
        new = fest.build_performance(body.model_dump())
        fest.add(new)
        persist(fest)
        return new.to_view()

    @app.put("/api/performances/{performance_id}")
    def update_performance(performance_id: str, body: PerformanceIn) -> dict:
        fest = festival()
        new = fest.build_performance(body.model_dump())
        fest.replace(performance_id, new)
        persist(fest)
        return new.to_view()

    @app.delete("/api/performances/{performance_id}", status_code=204)
    def delete_performance(performance_id: str) -> None:
        fest = festival()
        fest.cancel(performance_id)
        persist(fest)

    @app.post("/api/performances/{performance_id}/participants")
    def register_participant(performance_id: str, body: ParticipantIn) -> dict:
        fest = festival()
        workshop = fest.register(performance_id, body.name)
        persist(fest)
        return workshop.to_view()

    @app.post("/api/artists", status_code=201)
    def create_artist(body: ArtistIn) -> dict:
        fest = festival()
        artist = fest.add_artist(body.name, body.bio, body.photo_url)
        persist(fest)
        return artist.to_view()

    app.mount(
        "/admin",
        StaticFiles(directory="web/admin", html=True),
        name="admin",
    )
    app.mount("/", StaticFiles(directory="web/public", html=True), name="site")
    return app


app = create_app(JsonStorage(Path("data/festival.json")))
