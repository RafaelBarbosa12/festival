"""Every behaviour of API.md, without touching data/festival.json."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.festival import Festival
from deauville.storage import JsonStorage, Storage

SOURCE = Path(__file__).resolve().parent.parent / "data" / "festival.json"

NORA_SOLO = {
    "kind": "solo",
    "title": "Sunday Morning",
    "venue": "le-kiosque",
    "start": "2027-06-13T11:00",
    "duration_minutes": 45,
    "artist": "nora-lebrun",
    "min_age": 0,
}


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "festival.json"
    path.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    return path


@pytest.fixture
def client(data_file):
    return TestClient(create_app(JsonStorage(data_file)))


def test_source_data_is_not_the_temp_file(data_file):
    assert data_file.resolve() != SOURCE.resolve()


def test_get_festival(client):
    response = client.get("/api/festival")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Deauville Festival du Rire 2027"
    assert body["first_day"] == "2027-06-10"
    assert body["last_day"] == "2027-06-13"
    assert body["days"] == [
        "2027-06-10",
        "2027-06-11",
        "2027-06-12",
        "2027-06-13",
    ]


def test_get_venues_keeps_file_order(client):
    slugs = [row["slug"] for row in client.get("/api/venues").json()]
    assert slugs == [
        "grand-casino",
        "theatre-des-planches",
        "le-kiosque",
        "la-cabane",
    ]


def test_get_venue(client):
    response = client.get("/api/venues/le-kiosque")
    assert response.status_code == 200
    assert response.json()["name"] == "Le Kiosque"


def test_get_unknown_venue(client):
    response = client.get("/api/venues/nowhere")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_get_artists_sorted_by_slug(client):
    slugs = [row["slug"] for row in client.get("/api/artists").json()]
    assert slugs == sorted(slugs)
    assert slugs[0] == "elodie-marchal"


def test_get_artist_includes_performances(client):
    response = client.get("/api/artists/lea-fontaine")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Léa Fontaine"
    ids = [item["id"] for item in body["performances"]]
    assert "grand-casino-2027-06-11-2030" in ids


def test_get_unknown_artist(client):
    assert client.get("/api/artists/nobody").status_code == 404


def test_programme_of_friday_includes_after_hours(client):
    response = client.get("/api/programme", params={"day": "2027-06-11"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert "le-kiosque-2027-06-12-0100" in ids
    assert "grand-casino-2027-06-11-2030" in ids


def test_programme_filter_by_venue(client):
    response = client.get("/api/programme", params={"venue": "le-kiosque"})
    assert response.status_code == 200
    assert {item["venue"] for item in response.json()} == {"le-kiosque"}


def test_programme_unknown_venue(client):
    assert client.get("/api/programme", params={"venue": "nowhere"}).status_code == 404


def test_programme_invalid_day(client):
    response = client.get("/api/programme", params={"day": "June 11"})
    assert response.status_code == 422


def test_get_performance(client):
    response = client.get("/api/performances/grand-casino-2027-06-11-2030")
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "solo"
    assert body["artist"] == "lea-fontaine"
    assert body["summary"] == "Léa Fontaine"
    assert body["start"] == "2027-06-11T20:30"


def test_get_unknown_performance(client):
    assert client.get("/api/performances/missing").status_code == 404


def test_now_at_tall_tales(client):
    response = client.get("/api/now", params={"at": "2027-06-11T21:00"})
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["now_playing"]] == ["Tall Tales"]
    assert [item["title"] for item in body["up_next"]] == [
        "Straight Face",
        "Late Laughs",
        "After Hours",
    ]
    assert len(body["up_next"]) <= 3


def test_create_solo_show(client, data_file):
    response = client.post("/api/performances", json=NORA_SOLO)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "le-kiosque-2027-06-13-1100"
    saved = JsonStorage(data_file).load()
    assert saved.performance_by_id(body["id"]) is not None


def test_create_refused_when_venue_busy(client):
    assert client.post("/api/performances", json=NORA_SOLO).status_code == 201
    clash = {**NORA_SOLO, "title": "Too close", "start": "2027-06-13T11:30"}
    response = client.post("/api/performances", json=clash)
    assert response.status_code == 409
    assert "Le Kiosque is busy" in response.json()["detail"]


def test_create_refused_when_artist_busy(client):
    assert client.post("/api/performances", json=NORA_SOLO).status_code == 201
    elsewhere = {
        **NORA_SOLO,
        "title": "Elsewhere",
        "venue": "grand-casino",
        "start": "2027-06-13T12:00",
    }
    response = client.post("/api/performances", json=elsewhere)
    assert response.status_code == 409
    assert "Nora Lebrun is on stage" in response.json()["detail"]


def test_create_lineup_with_one_act(client):
    response = client.post(
        "/api/performances",
        json={
            "kind": "lineup",
            "title": "Thin",
            "venue": "la-cabane",
            "start": "2027-06-13T08:00",
            "duration_minutes": 60,
            "host": "paul-kerbrat",
            "acts": ["nora-lebrun"],
        },
    )
    assert response.status_code == 422
    assert "two acts" in response.json()["detail"]


def test_missing_body_field(client):
    response = client.post("/api/performances", json={"kind": "solo", "title": "Nope"})
    assert response.status_code == 422


def test_put_changes_the_id(client):
    created = client.post("/api/performances", json=NORA_SOLO).json()
    moved = {**NORA_SOLO, "start": "2027-06-13T12:00"}
    response = client.put(f"/api/performances/{created['id']}", json=moved)
    assert response.status_code == 200
    assert response.json()["id"] == "le-kiosque-2027-06-13-1200"
    assert client.get(f"/api/performances/{created['id']}").status_code == 404
    assert client.get("/api/performances/le-kiosque-2027-06-13-1200").status_code == 200


def test_put_refused_leaves_the_schedule(client):
    created = client.post("/api/performances", json=NORA_SOLO).json()
    moved = {**NORA_SOLO, "start": "2027-06-13T15:00"}
    response = client.put(f"/api/performances/{created['id']}", json=moved)
    assert response.status_code == 409
    still_there = client.get(f"/api/performances/{created['id']}")
    assert still_there.status_code == 200
    assert still_there.json()["title"] == "Sunday Morning"
    occupant = client.get("/api/performances/le-kiosque-2027-06-13-1500")
    assert occupant.status_code == 200
    assert occupant.json()["title"] == "First Time Here"


def test_delete_then_delete_again(client):
    created = client.post("/api/performances", json=NORA_SOLO)
    path = f"/api/performances/{created.json()['id']}"
    first = client.delete(path)
    assert first.status_code == 204
    assert first.content == b""
    second = client.delete(path)
    assert second.status_code == 404


def test_register_participant_then_duplicate(client):
    workshop_id = "la-cabane-2027-06-12-1030"
    first = client.post(
        f"/api/performances/{workshop_id}/participants",
        json={"name": "Zoé T."},
    )
    assert first.status_code == 200
    assert "Zoé T." in first.json()["participants"]
    second = client.post(
        f"/api/performances/{workshop_id}/participants",
        json={"name": "Zoé T."},
    )
    assert second.status_code == 409
    assert "already registered" in second.json()["detail"]


def test_register_on_a_full_workshop(client):
    created = client.post(
        "/api/performances",
        json={
            "kind": "workshop",
            "title": "One seat",
            "venue": "la-cabane",
            "start": "2027-06-13T08:00",
            "duration_minutes": 60,
            "teacher": "ines-moreau",
            "max_participants": 1,
        },
    )
    assert created.status_code == 201
    path = f"/api/performances/{created.json()['id']}/participants"
    assert client.post(path, json={"name": "Lou"}).status_code == 200
    full = client.post(path, json={"name": "Yanis"})
    assert full.status_code == 409
    assert "full" in full.json()["detail"]


def test_register_on_a_solo_is_invalid(client):
    response = client.post(
        "/api/performances/grand-casino-2027-06-11-2030/participants",
        json={"name": "Lou"},
    )
    assert response.status_code == 422


def test_add_artist_then_duplicate_slug(client):
    first = client.post("/api/artists", json={"name": "Zoé Tanguy"})
    assert first.status_code == 201
    assert first.json()["slug"] == "zoe-tanguy"
    second = client.post("/api/artists", json={"name": "zoe tanguy"})
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_cannot_write_the_data_file(data_file):
    class BrokenStorage(Storage):
        def load(self) -> Festival:
            return JsonStorage(data_file).load()

        def save(self, festival: Festival) -> None:
            raise OSError("disk full")

    client = TestClient(create_app(BrokenStorage()))
    response = client.post("/api/performances", json=NORA_SOLO)
    assert response.status_code == 500
    assert "Could not write" in response.json()["detail"]


def test_site_and_admin_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/admin/").status_code == 200
