const timelineEl = document.getElementById("timeline");
const template = document.getElementById("event-template");
const searchInput = document.getElementById("search");
const statusFilter = document.getElementById("status-filter");
const typeFilter = document.getElementById("type-filter");
const areaFilter = document.getElementById("area-filter");
const resultsCountEl = document.querySelector("[data-results-count]");
const themeToggle = document.querySelector("[data-theme-toggle]");
const themeColorMeta = document.querySelector('meta[name="theme-color"]');

const THEME_STORAGE_KEY = "lastCallDSMTheme";
const THEME_COLORS = {
  light: "#f5f4f1",
  dark: "#101110",
};

const state = {
  status: "all",
  venueType: "all",
  neighborhood: "all",
  search: "",
  items: [],
};

const STATUS_LABELS = {
  opened: "Opened",
  closed: "Closed",
  lastcall: "Last Call",
};

const ICONS = {
  light: {
    opened: "assets/open.svg",
    closed: "assets/closed.svg",
    lastcall: "assets/lastcall.svg",
  },
  dark: {
    opened: "assets/openWHITE.svg",
    closed: "assets/closedWHITE.svg",
    lastcall: "assets/lastcallWHITE.svg",
  },
};

function getPreferredTheme() {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  if (themeColorMeta) {
    themeColorMeta.setAttribute("content", THEME_COLORS[theme]);
  }
  if (themeToggle) {
    themeToggle.setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
    );
    themeToggle.setAttribute(
      "title",
      theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
    );
  }
  if (state.items.length) {
    renderTimeline();
  }
}

function iconForItem(status) {
  const theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  return ICONS[theme][status] || ICONS[theme].closed;
}

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

function buildMapUrl(item) {
  if (item.mapUrl) {
    return item.mapUrl;
  }

  const explicitAddress = [
    item.addressLine1,
    item.addressLine2,
    item.city,
    item.state,
    item.postalCode,
  ]
    .filter(Boolean)
    .join(", ");

  const query =
    item.mapQuery ||
    item.address ||
    explicitAddress ||
    [item.name, item.neighborhood, "Iowa"].filter(Boolean).join(", ");

  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
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

function syncControlValues() {
  searchInput.value = state.search;
  statusFilter.value = state.status;
  typeFilter.value = state.venueType;
  areaFilter.value = state.neighborhood;
}

function setFilterValue(filterName, value) {
  if (filterName === "status") {
    state.status = value;
  }
  if (filterName === "type") {
    state.venueType = value;
  }
  if (filterName === "area") {
    state.neighborhood = value;
  }
  syncControlValues();
  renderTimeline();
}

function toggleFilterValue(filterName, value) {
  if (filterName === "status") {
    setFilterValue("status", state.status === value ? "all" : value);
    return;
  }
  if (filterName === "type") {
    setFilterValue("type", state.venueType === value ? "all" : value);
    return;
  }
  if (filterName === "area") {
    setFilterValue("area", state.neighborhood === value ? "all" : value);
  }
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
      item.address,
      item.addressLine1,
      item.city,
      item.state,
      item.mapQuery,
      item.cuisine,
      item.story,
      item.publicDescription,
      item.venueTypeLabel,
      item.dateLabel,
      item.openedDate,
      item.closedDate,
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
    const nameLink = fragment.querySelector('[data-field="name-link"]');
    const statusChip = fragment.querySelector('[data-field="status-chip"]');
    const typeChip = fragment.querySelector('[data-field="type-chip"]');
    const areaChip = fragment.querySelector('[data-field="area-chip"]');

    icon.src = iconForItem(item.status);
    fragment.querySelector('[data-field="range"]').textContent = buildRange(item);
    fragment.querySelector('[data-field="name"]').textContent = item.name;
    fragment.querySelector('[data-field="description"]').textContent = buildDescription(item);
    nameLink.href = buildMapUrl(item);
    nameLink.setAttribute("aria-label", `Open directions for ${item.name}`);

    statusChip.textContent = (STATUS_LABELS[item.status] || item.status).toUpperCase();
    statusChip.setAttribute("aria-label", `Filter status by ${STATUS_LABELS[item.status] || item.status}`);
    const statusSelected = state.status === item.status;
    statusChip.classList.toggle("is-active", statusSelected);
    statusChip.setAttribute("aria-pressed", String(statusSelected));
    statusChip.addEventListener("click", () => {
      toggleFilterValue("status", item.status);
    });

    typeChip.textContent = item.venueTypeLabel.toUpperCase();
    typeChip.setAttribute("aria-label", `Filter type by ${item.venueTypeLabel}`);
    const typeSelected = state.venueType === item.venueType;
    typeChip.classList.toggle("is-active", typeSelected);
    typeChip.setAttribute("aria-pressed", String(typeSelected));
    typeChip.addEventListener("click", () => {
      toggleFilterValue("type", item.venueType);
    });

    areaChip.textContent = item.neighborhood.toUpperCase();
    areaChip.setAttribute("aria-label", `Filter area by ${item.neighborhood}`);
    const areaSelected = state.neighborhood === item.neighborhood;
    areaChip.classList.toggle("is-active", areaSelected);
    areaChip.setAttribute("aria-pressed", String(areaSelected));
    areaChip.addEventListener("click", () => {
      toggleFilterValue("area", item.neighborhood);
    });

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
    "All",
  );
  populateSelect(
    areaFilter,
    neighborhoods,
    Object.fromEntries(state.items.map((item) => [item.neighborhood, item.neighborhood])),
    "All",
  );

  syncControlValues();
  renderTimeline();
}

function bindEvents() {
  const updateSearch = (value) => {
    state.search = value.trim();
    syncControlValues();
    renderTimeline();
  };

  searchInput.addEventListener("input", (event) => {
    updateSearch(event.target.value);
  });

  statusFilter.addEventListener("change", (event) => {
    setFilterValue("status", event.target.value);
  });

  typeFilter.addEventListener("change", (event) => {
    setFilterValue("type", event.target.value);
  });

  areaFilter.addEventListener("change", (event) => {
    setFilterValue("area", event.target.value);
  });

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const nextTheme =
        document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
    });
  }
}

applyTheme(getPreferredTheme());
bindEvents();
loadData().catch((error) => {
  console.error(error);
  timelineEl.innerHTML =
    '<p class="empty-state">Unable to load the public timeline right now.</p>';
});
