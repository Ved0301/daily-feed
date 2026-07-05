const SECTIONS = [
  { key: "research",   label: "Research Papers" },
  { key: "labs",       label: "From the Labs" },
  { key: "startups",   label: "Startups & Business" },
  { key: "wider_tech", label: "Wider Tech" },
];

// Change this to the date you first published the site — powers the "Issue No." counter.
const LAUNCH_DATE = new Date("2026-07-05T00:00:00Z");

function issueNumber() {
  const days = Math.floor((Date.now() - LAUNCH_DATE) / 86400000) + 1;
  return String(Math.max(days, 1)).padStart(3, "0");
}

function formatMasthead(date) {
  return date.toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });
}

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diffMs / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function renderSection(section, items) {
  const wrap = document.createElement("div");
  wrap.className = "section";

  const label = document.createElement("div");
  label.className = "section-label";
  label.innerHTML = `${section.label} <span class="section-count">(${items.length})</span>`;
  wrap.appendChild(label);

  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "loading";
    empty.textContent = "Nothing new here yet — check back tomorrow.";
    wrap.appendChild(empty);
    return wrap;
  }

  items.forEach((item) => {
    const a = document.createElement("a");
    a.className = "item";
    a.href = item.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";

    a.innerHTML = `
      <p class="item-title">${item.title}</p>
      ${item.summary ? `<p class="item-summary">${item.summary}</p>` : ""}
      <p class="item-meta">${item.source}<span class="dot">·</span>${timeAgo(item.date)}</p>
    `;
    wrap.appendChild(a);
  });

  return wrap;
}

async function init() {
  document.getElementById("issue-number").textContent = issueNumber();
  document.getElementById("masthead-date").textContent = formatMasthead(new Date());

  const content = document.getElementById("content");

  try {
    const res = await fetch("data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    content.innerHTML = "";
    SECTIONS.forEach((section) => {
      const items = data.sections[section.key] || [];
      content.appendChild(renderSection(section, items));
    });

    document.getElementById("footer-updated").textContent =
      new Date(data.generated_at).toLocaleString("en-US", {
        dateStyle: "medium", timeStyle: "short",
      });
  } catch (err) {
    content.innerHTML = `<p class="error">Couldn't load today's feed (${err.message}). If you just deployed this, run the fetcher once — see README.</p>`;
  }
}

init();
