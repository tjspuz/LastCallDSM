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

const STATUS_LABELS = {
  opened: "Opened",
  closed: "Closed",
  lastcall: "Last Call",
};

const ICONS = {
  opened: "assets/open.svg",
  closed: "assets/closed.svg",
  lastcall: "assets/lastcall.svg",
};

function parseDate(value) {
  return new Date(`${value}T12:00:00`);
}

function normalizeSpaces(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function formatShortDate(value, precision = "month") {
  if (!value) {
    return "";
  }

  const [year, month = "01", day = "01"] = value.split("-");
  if (precision === "day") {
    return `${month}/${day}/${year}`;
  }
  if (precision === "month") {
    return `${month}/${year}`;
  }
  return year;
}

function formatLongDate(value, precision = "month") {
  if (!value) {
    return "";
  }

  const parsed = parseDate(value);
  if (precision === "day") {
    return parsed.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }
  if (precision === "month") {
    return parsed.toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });
  }
  return String(parsed.getFullYear());
}

function buildRange(item) {
  const openedDate = item.openedDate;
  const openedPrecision = item.openedDatePrecision || "year";
  const closedDate = item.closedDate || item.eventDate;
  const closedPrecision = item.closedDatePrecision || item.datePrecision || "month";

  if (openedDate && closedDate && item.status !== "opened") {
    return `${formatShortDate(openedDate, openedPrecision)} - ${formatShortDate(
      closedDate,
      closedPrecision,
    )}`;
  }

  if (openedDate && item.status === "opened") {
    return `${formatShortDate(openedDate, openedPrecision)} - present`;
  }

  if (item.status === "lastcall" && closedDate) {
    return `Closes ${formatShortDate(closedDate, closedPrecision)}`;
  }

  if (closedDate) {
    return formatShortDate(closedDate, closedPrecision);
  }

  return item.dateLabel || "";
}

function buildKicker(item) {
  const parts = [];
  if (item.neighborhood) {
    parts.push(item.neighborhood);
  }
  parts.push(STATUS_LABELS[item.status] || item.status);
  return parts.join(" / ");
}

function buildDescription(item) {
  let description = normalizeSpaces(item.publicDescription || item.story || "");

  description = description
    .replace(/^Automatically verified from the lead pipeline\.\s*/i, "")
    .replace(/^Matched facility-specific coverage for\s*/i, "")
    .replace(/Confirmation source:\s*news\.google\.com\.?/i, "")
    .trim();

  if (
    item.status === "lastcall" &&
    item.closedDate &&
    item.closedDatePrecision === "day" &&
    !new RegExp(formatLongDate(item.closedDate, "day"), "i").test(description)
  ) {
    description = `Last call is ${formatLongDate(item.closedDate, "day")}. ${description}`.trim();
  }

  if (!description) {
    const type = (item.cuisine && item.cuisine !== "Category Pending")
      ? item.cuisine
      : item.venueTypeLabel.toLowerCase();
    if (item.status === "opened") {
      description = `${item.name} opened as a ${type} in ${item.neighborhood}.`;
    } else if (item.status === "lastcall") {
      description = `${item.name} is preparing to close in ${item.neighborhood}.`;
    } else {
      description = `${item.name} closed after a run in ${item.neighborhood}.`;
    }
  }

  if (description.length > 175) {
    const clipped = description.slice(0, 172);
    return `${clipped.slice(0, clipped.lastIndexOf(" "))}...`;
  }

  return description;
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
      item.publicDescription,
      item.venueTypeLabel,
      item.dateLabel,
      item.openedDate,
      item.closedDate,
      item.verificationLevel,
      ...item.sources.map((source) => source.label),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(state.search.toLowerCase());
  });
}

function renderTimeline() {
  const items = filteredItems();
  resultsCountEl.textContent = `${items.length} record${items.length === 1 ? "" : "s"}`;
  timelineEl.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent =
      "No records match the current filters. Try broadening the dropdowns or search.";
    timelineEl.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const fragment = template.content.cloneNode(true);
    const icon = fragment.querySelector('[data-field="icon"]');

    icon.src = ICONS[item.status] || ICONS.closed;
    fragment.querySelector('[data-field="range"]').textContent = buildRange(item);
    fragment.querySelector('[data-field="type"]').textContent = item.venueTypeLabel;
    fragment.querySelector('[data-field="kicker"]').textContent = buildKicker(item);
    fragment.querySelector('[data-field="name"]').textContent = item.name;
    fragment.querySelector('[data-field="description"]').textContent = buildDescription(item);

    timelineEl.appendChild(fragment);
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
    Object.fromEntries(state.items.map((item) => [item.neighborhood, item.neighborhood])),
    "All areas",
  );

  renderTimeline();
}

function bindEvents() {
  searchInput.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderTimeline();
  });

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
}

bindEvents();
loadData().catch((error) => {
  console.error(error);
  timelineEl.innerHTML =
    '<p class="empty-state">Unable to load the public timeline right now.</p>';
});
