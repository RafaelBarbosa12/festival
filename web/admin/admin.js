const flash = document.getElementById("flash");

function showFlash(text, isError) {
  flash.hidden = false;
  flash.textContent = text;
  flash.classList.toggle("error", Boolean(isError));
}

async function send(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = response.status === 204 ? {} : await response.json();
  if (!response.ok) {
    throw new Error(body.detail || response.statusText);
  }
  return body;
}

async function refresh() {
  const shows = await send("/api/programme");
  const list = document.getElementById("schedule");
  list.replaceChildren();
  for (const show of shows) {
    const item = document.createElement("li");
    item.textContent = `${show.id} — ${show.title} (${show.kind})`;
    list.append(item);
  }
}

document.getElementById("solo-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    const created = await send("/api/performances", {
      method: "POST",
      body: JSON.stringify({
        kind: "solo",
        title: data.title,
        artist: data.artist,
        venue: data.venue,
        start: data.start,
        duration_minutes: Number(data.duration_minutes),
        min_age: 0,
      }),
    });
    showFlash(`Added ${created.id}`);
    event.target.reset();
    await refresh();
  } catch (error) {
    showFlash(error.message, true);
  }
});

document.getElementById("lineup-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    const created = await send("/api/performances", {
      method: "POST",
      body: JSON.stringify({
        kind: "lineup",
        title: data.title,
        host: data.host,
        acts: data.acts.split(",").map((slug) => slug.trim()).filter(Boolean),
        venue: data.venue,
        start: data.start,
        duration_minutes: Number(data.duration_minutes),
      }),
    });
    showFlash(`Added ${created.id}`);
    event.target.reset();
    await refresh();
  } catch (error) {
    showFlash(error.message, true);
  }
});

document.getElementById("move-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    const current = await send(`/api/performances/${encodeURIComponent(data.id)}`);
    const moved = await send(`/api/performances/${encodeURIComponent(data.id)}`, {
      method: "PUT",
      body: JSON.stringify({ ...current, start: data.start, venue: current.venue }),
    });
    showFlash(`Moved to ${moved.id}`);
    event.target.reset();
    await refresh();
  } catch (error) {
    showFlash(error.message, true);
  }
});

document.getElementById("cancel-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    const response = await fetch(
      `/api/performances/${encodeURIComponent(data.id)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || response.statusText);
    }
    showFlash(`Cancelled ${data.id}`);
    event.target.reset();
    await refresh();
  } catch (error) {
    showFlash(error.message, true);
  }
});

document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    await send(`/api/performances/${encodeURIComponent(data.id)}/participants`, {
      method: "POST",
      body: JSON.stringify({ name: data.name }),
    });
    showFlash(`Registered ${data.name}`);
    event.target.reset();
    await refresh();
  } catch (error) {
    showFlash(error.message, true);
  }
});

document.getElementById("artist-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    const artist = await send("/api/artists", {
      method: "POST",
      body: JSON.stringify({ name: data.name }),
    });
    showFlash(`Added ${artist.slug}`);
    event.target.reset();
  } catch (error) {
    showFlash(error.message, true);
  }
});

refresh();
