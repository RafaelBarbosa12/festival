function clock(iso) {
  return iso.slice(11, 16);
}

async function main() {
  const slug = new URLSearchParams(window.location.search).get("slug");
  const response = await fetch(`/api/artists/${encodeURIComponent(slug)}`);
  if (!response.ok) {
    document.getElementById("artist-name").textContent = "Unknown artist";
    return;
  }
  const artist = await response.json();
  document.title = `${artist.name} — Deauville Festival du Rire`;
  document.getElementById("artist-name").textContent = artist.name;
  document.getElementById("artist-bio").textContent = artist.bio;

  const list = document.getElementById("shows");
  const empty = document.getElementById("shows-empty");
  empty.classList.toggle("hidden", artist.performances.length > 0);
  for (const show of artist.performances) {
    const article = document.createElement("article");
    article.className = "show-card";
    article.innerHTML = `
      <p class="when">${show.festival_day} · ${clock(show.start)}–${clock(show.end)} · ${show.venue_name}${show.min_age > 0 ? ` · ${show.min_age}+` : ""}${show.places_left != null ? ` · ${show.places_left} place(s) left` : ""}</p>
      <h3>${show.title}</h3>
      <p class="kind">${show.kind}</p>
      <p>${show.summary}</p>
    `;
    list.append(article);
  }
}

main();
