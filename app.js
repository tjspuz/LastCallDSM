const timelineEl = document.getElementById("timeline");
const template = document.getElementById("event-template");
const searchInput = document.getElementById("search");
const statusFilter = document.getElementById("status-filter");
const typeFilter = document.getElementById("type-filter");
const areaFilter = document.getElementById("area-filter");
const verificationFilter = document.getElementById("verification-filter");
const resultsCountEl = document.querySelector("[data-results-count]");

const state = {
  status: "all",
  venueType: "all",
  neighborhood: "all",
  verificationLevel: "all",
  search: "",
  items: [],
};

function parseDate(value) {
  return new Date(`${value}T12:00:00`);
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function buildKicker(item) {
  const parts = [item.neighborhood, item.cuisine || item.venueTypeLabel];
  return parts.filter(Boolean).join(" / ");
}

function buildMeta(item) {
  const parts = [];
  if (item.datePrecision === "year") {
    parts.push(`Year-level date`);
  } else if (item.datePrecision === "month") {
    parts.push(`Month-level date`);
  }
  if (item.verificationLevel === "review") {
    parts.push("Still needs stronger sourcing");
  }
  return parts.join(" • ");
}

function populateSelect(select, values, labels, allLabel) {
  select.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = allLabel;
  select.appendChild(allOption);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labels[value] || value;
    select.appendChild(option);
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

    if (
      state.verificationLevel !== "all" &&
      item.verificationLevel !== state.verificationLevel
    ) {
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
      item.verificationLevel,
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
  resultsCountEl.textContent = `${items.length} result${items.length === 1 ? "" : "s"}`;
  timelineEl.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent =
      "No records match the current filters. Try broadening the search or switching the dropdowns back to all.";
    timelineEl.appendChild(empty);
    return;
  }

  const grouped = new Map();
  items.forEach((item) => {
    const year = item.eventDate.slice(0, 4);
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
      const article = fragment.querySelector(".entry-card");
      const statusBadge = fragment.querySelector('[data-field="status"]');
      const verificationBadge = fragment.querySelector('[data-field="verification"]');

      fragment.querySelector('[data-field="icon"]').textContent =
        item.status === "closed" ? "⚰" : "✦";
      fragment.querySelector('[data-field="date"]').textContent = item.dateLabel;
      fragment.querySelector('[data-field="type"]').textContent = item.venueTypeLabel.toLowerCase();
      fragment.querySelector('[data-field="kicker"]').textContent = buildKicker(item);
      fragment.querySelector('[data-field="name"]').textContent = item.name;
      fragment.querySelector('[data-field="story"]').textContent = item.story;
      fragment.querySelector('[data-field="meta"]').textContent = buildMeta(item);

      const sourcesEl = fragment.querySelector('[data-field="sources"]');
      sourcesEl.textContent = "";
      item.sources.forEach((source, index) => {
        if (index > 0) {
          sourcesEl.appendChild(document.createTextNode(" / "));
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

      statusBadge.textContent = item.status === "closed" ? "Closed" : "Opened";
      statusBadge.classList.add(item.status);

      verificationBadge.textContent =
        item.verificationLevel === "verified" ? "Verified" : "Review";
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

  populateSelect(
    typeFilter,
    venueTypes,
    Object.fromEntries(state.items.map((item) => [item.venueType, item.venueTypeLabel])),
    "All types",
  );
  populateSelect(
    areaFilter,
    neighborhoods,
    Object.fromEntries(neighborhoods.map((value) => [value, value])),
    "All areas",
  );

  renderTimeline();
}

statusFilter.addEventListener("change", (event) => {
  state.status = event.target.value;
  renderTimeline();
});

typeFilter.addEventListener("change", (event) => {
  state.venueType = event.target.value;
  renderTimeline();
});

areaFilter.addEventListener("change", (event) => {
  state.neighborhood = event.target.value;
  renderTimeline();
});

verificationFilter.addEventListener("change", (event) => {
  state.verificationLevel = event.target.value;
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
