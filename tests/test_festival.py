"""Rules of the festival: one test per rule of the brief."""

from datetime import date, datetime
from pathlib import Path

import pytest

from deauville.errors import ConflictError, InvalidError, NotFoundError
from deauville.models import Lineup, Performance, SoloShow, Workshop
from deauville.storage import JsonStorage

DATA = Path(__file__).resolve().parent.parent / "data" / "festival.json"


@pytest.fixture
def festival():
    return JsonStorage(DATA).load()


def solo(festival, title, artist_slug, venue_slug, start, minutes):
    return SoloShow(
        title=title,
        venue=festival.venue_by_slug(venue_slug),
        start=datetime.fromisoformat(start),
        duration_minutes=minutes,
        artist=festival.artist_by_slug(artist_slug),
        min_age=0,
    )


def test_venue_busy(festival):
    new = solo(
        festival,
        "Too Late",
        "karim-benali",
        "le-kiosque",
        "2027-06-12T02:15",
        30,
    )
    with pytest.raises(ConflictError, match="Le Kiosque is busy"):
        festival.add(new)


def test_artist_busy_in_another_venue(festival):
    new = solo(
        festival,
        "Clash",
        "max-pellerin",
        "la-cabane",
        "2027-06-11T23:00",
        30,
    )
    with pytest.raises(ConflictError, match="Max Pellerin is on stage"):
        festival.add(new)


def test_artist_busy_as_act_of_a_lineup(festival):
    new = solo(
        festival,
        "Double booked",
        "max-pellerin",
        "la-cabane",
        "2027-06-10T21:00",
        30,
    )
    with pytest.raises(ConflictError, match="Max Pellerin is on stage"):
        festival.add(new)


def test_show_at_01_00_belongs_to_the_previous_day(festival):
    after_hours = festival.performance_by_id("le-kiosque-2027-06-12-0100")
    assert after_hours.festival_day == date(2027, 6, 11)
    friday = festival.programme(day=date(2027, 6, 11))
    saturday = festival.programme(day=date(2027, 6, 12))
    assert after_hours in friday
    assert after_hours not in saturday


def test_day_outside_the_festival(festival):
    new = solo(
        festival,
        "Too far",
        "karim-benali",
        "la-cabane",
        "2027-06-14T08:00",
        30,
    )
    with pytest.raises(ConflictError, match="2027-06-14 is not a day"):
        festival.add(new)


@pytest.mark.parametrize("minutes", [0, 361])
def test_duration_must_be_between_1_and_360(festival, minutes):
    new = solo(
        festival,
        "Wrong length",
        "karim-benali",
        "la-cabane",
        "2027-06-13T08:00",
        minutes,
    )
    with pytest.raises(InvalidError, match="1 to 360"):
        festival.add(new)


def test_unknown_venue(festival):
    with pytest.raises(NotFoundError, match="No venue"):
        festival.add_solo(
            "Ghost room",
            "karim-benali",
            "nowhere",
            datetime(2027, 6, 13, 8, 0),
            30,
        )


def test_unknown_artist(festival):
    with pytest.raises(NotFoundError, match="No artist"):
        festival.add_solo(
            "Ghost act",
            "nobody",
            "la-cabane",
            datetime(2027, 6, 13, 8, 0),
            30,
        )


def test_now_playing_tall_tales(festival):
    at = datetime(2027, 6, 11, 21, 0)
    playing = [item.title for item in festival.now_playing(at)]
    upcoming = [item.title for item in festival.up_next(at)]
    assert playing == ["Tall Tales"]
    assert upcoming == ["Straight Face", "Late Laughs", "After Hours"]


def test_summaries(festival):
    after_hours = festival.performance_by_id("le-kiosque-2027-06-12-0100")
    workshop = festival.performance_by_id("la-cabane-2027-06-11-1030")
    tall_tales = festival.performance_by_id("grand-casino-2027-06-11-2030")
    assert after_hours.summary() == (
        "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri"
    )
    assert workshop.summary() == "with Inès Moreau, 3/12 places taken"
    assert tall_tales.summary() == "Léa Fontaine"


def test_lineup_of_3_acts_needs_36_minutes(festival):
    venue = festival.venue_by_slug("la-cabane")
    host = festival.artist_by_slug("paul-kerbrat")
    acts = [
        festival.artist_by_slug("nora-lebrun"),
        festival.artist_by_slug("lea-fontaine"),
        festival.artist_by_slug("karim-benali"),
    ]
    start = datetime(2027, 6, 13, 8, 0)
    with pytest.raises(InvalidError, match="at least 36 minutes"):
        Lineup("Too short", venue, start, 35, host, acts)
    show = Lineup("Just enough", venue, start, 36, host, acts)
    assert show.duration_minutes == 36


def test_lineup_needs_two_distinct_acts(festival):
    venue = festival.venue_by_slug("la-cabane")
    host = festival.artist_by_slug("paul-kerbrat")
    nora = festival.artist_by_slug("nora-lebrun")
    start = datetime(2027, 6, 13, 8, 0)
    with pytest.raises(InvalidError, match="at least two acts"):
        Lineup("Solo lineup", venue, start, 60, host, [nora])
    with pytest.raises(InvalidError, match="only once"):
        Lineup("Twice", venue, start, 60, host, [nora, nora])
    with pytest.raises(InvalidError, match="host cannot"):
        Lineup("Host on stage", venue, start, 60, host, [host, nora])


def test_workshop_places_capped_by_venue_seats(festival):
    venue = festival.venue_by_slug("grand-casino")
    teacher = festival.artist_by_slug("ines-moreau")
    workshop = Workshop(
        "Huge room",
        venue,
        datetime(2027, 6, 13, 8, 0),
        60,
        teacher,
        999,
    )
    assert workshop.places == 650


def test_cannot_create_a_bare_performance(festival):
    venue = festival.venue_by_slug("la-cabane")
    with pytest.raises(TypeError):
        Performance("Nope", venue, datetime(2027, 6, 13, 8, 0), 30)


def test_append_on_the_copy_does_not_bypass_the_rules(festival):
    before = len(festival.performances)
    festival.performances.append(
        solo(
            festival,
            "Sneaky",
            "karim-benali",
            "la-cabane",
            "2027-06-13T08:00",
            30,
        )
    )
    assert len(festival.performances) == before


def test_refused_move_leaves_the_schedule(festival):
    old_id = "grand-casino-2027-06-11-2030"
    old = festival.require_performance(old_id)
    moved = SoloShow(
        old.title,
        old.venue,
        datetime(2027, 6, 12, 20, 30),
        old.duration_minutes,
        old.artist,
        old.min_age,
        old.description,
    )
    with pytest.raises(ConflictError):
        festival.replace(old_id, moved)
    assert festival.performance_by_id(old_id) is old
    saturday = festival.performance_by_id("grand-casino-2027-06-12-2030")
    assert saturday is not None
    assert saturday.title == "Nothing Serious"


def test_workshop_register_refuses_duplicates_and_a_full_room(festival):
    workshop = festival.require_performance("la-cabane-2027-06-11-1030")
    with pytest.raises(ConflictError, match="already registered"):
        workshop.register("Camille R.")
    with pytest.raises(ConflictError, match="already registered"):
        workshop.register("camille r.")
    tiny = Workshop(
        "Tiny",
        festival.venue_by_slug("la-cabane"),
        datetime(2027, 6, 13, 8, 0),
        60,
        festival.artist_by_slug("ines-moreau"),
        1,
    )
    tiny.register("Lou")
    with pytest.raises(ConflictError, match="full"):
        tiny.register("Yanis")


def test_artist_slug_must_be_unique(festival):
    festival.add_artist("Zoé Tanguy")
    with pytest.raises(ConflictError, match="already exists"):
        festival.add_artist("zoe tanguy")
