const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function formatDay(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return `${WEEKDAYS[date.getUTCDay()]} ${day} June`;
}

function clock(iso) {
  return iso.slice(11, 16);
}

async function readJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    return null;
  }
  return response.json();
}

function initials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("");
}

function badges(show) {
  const parts = [];
  if (show.min_age > 0) {
    parts.push(`<span class="badge">${show.min_age}+</span>`);
  }
  if (show.places_left != null) {
    parts.push(`<span class="badge">${show.places_left} place(s) left</span>`);
  }
  return parts.join(" ");
}

function showCard(show) {
  const article = document.createElement("article");
  article.className = "show-card";
  article.innerHTML = `
    <p class="when">${clock(show.start)}–${clock(show.end)} · ${show.venue_name} ${badges(show)}</p>
    <h3>${show.title}</h3>
    <p class="kind">${show.kind}</p>
    <p>${show.summary}</p>
  `;
  return article;
}

async function loadProgramme(day, venue) {
  const params = new URLSearchParams();
  if (day) {
    params.set("day", day);
  }
  if (venue) {
    params.set("venue", venue);
  }
  const shows = (await readJson(`/api/programme?${params}`)) ?? [];
  const list = document.getElementById("programme");
  const empty = document.getElementById("programme-empty");
  list.replaceChildren();
  empty.classList.toggle("hidden", shows.length > 0);
  for (const show of shows) {
    list.append(showCard(show));
  }
}

async function main() {
  const festival = await readJson("/api/festival");
  const venues = (await readJson("/api/venues")) ?? [];
  const artists = (await readJson("/api/artists")) ?? [];
  const tabs = document.getElementById("day-tabs");
  const select = document.getElementById("venue-select");

  if (festival) {
    document.getElementById("festival-name").textContent = festival.name;
    document.getElementById("festival-dates").textContent =
      `From ${festival.first_day} to ${festival.last_day}`;
  }

  for (const day of festival?.days ?? []) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = formatDay(day);
    button.dataset.day = day;
    if (day === festival.days[0]) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => {
      for (const other of tabs.querySelectorAll("button")) {
        other.classList.toggle("active", other === button);
      }
      loadProgramme(day, select.value);
    });
    tabs.append(button);
  }

  for (const venue of venues) {
    const option = document.createElement("option");
    option.value = venue.slug;
    option.textContent = `${venue.name} · ${venue.capacity} seats`;
    select.append(option);
  }
  select.addEventListener("change", () => {
    const active = tabs.querySelector("button.active");
    loadProgramme(active?.dataset.day, select.value);
  });

  const grid = document.getElementById("artists");
  for (const artist of artists) {
    const card = document.createElement("a");
    card.className = "artist-card";
    card.href = `/artist.html?slug=${encodeURIComponent(artist.slug)}`;
    card.innerHTML = `<strong>${initials(artist.name)} · ${artist.name}</strong><span>${artist.bio}</span>`;
    grid.append(card);
  }

  const at = new URLSearchParams(window.location.search).get("at");
  const nowPath = at ? `/api/now?at=${encodeURIComponent(at)}` : "/api/now";
  const now = await readJson(nowPath);
  if (now) {
    document.getElementById("now-when").textContent = `At ${now.at.replace("T", " ")}`;
    const playing = document.getElementById("now-playing");
    for (const show of now.now_playing) {
      playing.append(showCard(show));
    }
    if (now.now_playing.length === 0) {
      playing.innerHTML = "<p class='empty'>Nothing on stage.</p>";
    }
    const next = document.getElementById("up-next");
    for (const show of now.up_next) {
      next.append(showCard(show));
    }
  }

  await loadProgramme(festival?.days[0], "");
}

main();
