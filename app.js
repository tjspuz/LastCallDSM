const timelineEl = document.getElementById("timeline");
const template = document.getElementById("event-template");
const searchInput = document.getElementById("search");

const state = {
  status: "all",
  venueType: "all",
  neighborhood: "all",
  search: "",
  items: [],
};

function parseDate(value) {
  return new Date(`${value}T12:00:00`);
}

function buildMeta(item) {
  const parts = [item.venueTypeLabel, item.neighborhood];
  if (item.cuisine) {
    parts.push(item.cuisine);
  }
  return parts.filter(Boolean).join(" • ");
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function setActiveChip(group, value) {
  document.querySelectorAll(`[data-filter-group="${group}"]`).forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.value === value);
  });
}

function renderFilterGroup({ containerId, group, values, labels }) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  const allButton = document.createElement("button");
  allButton.className = "chip active";
  allButton.dataset.filterGroup = group;
  allButton.dataset.value = "all";
  allButton.textContent = "All";
  container.appendChild(allButton);

  values.forEach((value) => {
    const button = document.createElement("button");
    button.className = "chip";
    button.dataset.filterGroup = group;
    button.dataset.value = value;
    button.textContent = labels[value] || value;
    container.appendChild(button);
  });
}

function filteredItems() {
  return state.items.filter((item) => {
    if (state.status !== "all" && item.status !== state.status) {
      return false;
    }

    if (state.venueType !== "all" && item.venueType !== state.venueType) {
      return false;
    }

    if (state.neighborhood !== "all" && item.neighborhood !== state.neighborhood) {
      return false;
    }

    if (!state.search) {
      return true;
    }

    const haystack = [
      item.name,
      item.neighborhood,
      item.cuisine,
      item.story,
      item.venueTypeLabel,
      item.dateLabel,
      ...item.sources.map((source) => source.label),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(state.search.toLowerCase());
  });
}

function updateStats(items) {
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const totals = {
    total: items.length,
    closed: items.filter((item) => item.status === "closed").length,
    opened: items.filter((item) => item.status === "opened").length,
    month: items.filter((item) => item.eventDate.startsWith(currentMonth)).length,
  };

  document.querySelector('[data-stat="total"]').textContent = totals.total;
  document.querySelector('[data-stat="closed"]').textContent = totals.closed;
  document.querySelector('[data-stat="opened"]').textContent = totals.opened;
  document.querySelector('[data-stat="month"]').textContent = totals.month;
}

function renderTimeline() {
  const items = filteredItems();
  updateStats(items);
  timelineEl.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent =
      "No venues match the current filters yet. Try broadening the area or status filters.";
    timelineEl.appendChild(empty);
    return;
  }

  const grouped = new Map();
  items.forEach((item) => {
    const year = item.dateLabel.slice(-4);
    if (!grouped.has(year)) {
      grouped.set(year, []);
    }
    grouped.get(year).push(item);
  });

  Array.from(grouped.entries()).forEach(([year, yearItems]) => {
    const section = document.createElement("section");
    section.className = "year-group";

    const heading = document.createElement("h2");
    heading.className = "year-heading";
    heading.textContent = year;
    section.appendChild(heading);

    const list = document.createElement("div");
    list.className = "events";

    yearItems.forEach((item) => {
      const fragment = template.content.cloneNode(true);
      const article = fragment.querySelector(".event-card");
      const statusBadge = fragment.querySelector('[data-field="status"]');
      const verificationBadge = fragment.querySelector('[data-field="verification"]');

      fragment.querySelector('[data-field="icon"]').textContent =
        item.status === "closed" ? "🪦" : "🎉";
      fragment.querySelector('[data-field="name"]').textContent = item.name;
      fragment.querySelector('[data-field="meta"]').textContent = buildMeta(item);
      fragment.querySelector('[data-field="story"]').textContent = item.story;
      fragment.querySelector('[data-field="date"]').textContent = item.dateLabel;

      const sourcesEl = fragment.querySelector('[data-field="sources"]');
      sourcesEl.textContent = "via ";
      item.sources.forEach((source, index) => {
        if (index > 0) {
          sourcesEl.appendChild(document.createTextNode(" • "));
        }
        if (source.url) {
          const link = document.createElement("a");
          link.href = source.url;
          link.target = "_blank";
          link.rel = "noreferrer";
          link.textContent = source.label;
          sourcesEl.appendChild(link);
        } else {
          sourcesEl.appendChild(document.createTextNode(source.label));
        }
      });

      statusBadge.textContent = titleCase(item.status);
      statusBadge.classList.add(item.status);

      verificationBadge.textContent =
        item.verificationLevel === "verified" ? "Verified" : "In Review";
      verificationBadge.classList.add(
        item.verificationLevel === "verified" ? "verified" : "review",
      );

      article.dataset.status = item.status;
      article.dataset.type = item.venueType;
      article.dataset.neighborhood = item.neighborhood;
      list.appendChild(fragment);
    });

    section.appendChild(list);
    timelineEl.appendChild(section);
  });
}

async function loadData() {
  const response = await fetch("data/venues.json");
  const payload = await response.json();
  state.items = payload.items
    .slice()
    .sort((left, right) => parseDate(right.sortDate) - parseDate(left.sortDate));

  const venueTypes = Array.from(new Set(state.items.map((item) => item.venueType)));
  const neighborhoods = Array.from(new Set(state.items.map((item) => item.neighborhood)));

  renderFilterGroup({
    containerId: "type-filters",
    group: "venueType",
    values: venueTypes,
    labels: Object.fromEntries(
      state.items.map((item) => [item.venueType, item.venueTypeLabel]),
    ),
  });

  renderFilterGroup({
    containerId: "area-filters",
    group: "neighborhood",
    values: neighborhoods,
    labels: Object.fromEntries(neighborhoods.map((value) => [value, value])),
  });

  renderTimeline();
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-filter-group]");
  if (!target) {
    return;
  }

  const group = target.dataset.filterGroup;
  const value = target.dataset.value;
  state[group] = value;
  setActiveChip(group, value);
  renderTimeline();
});

searchInput.addEventListener("input", (event) => {
  state.search = event.target.value.trim();
  renderTimeline();
});

loadData().catch((error) => {
  timelineEl.innerHTML = "";
  const failure = document.createElement("p");
  failure.className = "empty-state";
  failure.textContent = `Unable to load venue data: ${error.message}`;
  timelineEl.appendChild(failure);
});
