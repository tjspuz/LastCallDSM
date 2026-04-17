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

const NUMBER_WORDS = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  thirteen: 13,
  fourteen: 14,
  fifteen: 15,
  sixteen: 16,
  seventeen: 17,
  eighteen: 18,
  nineteen: 19,
  twenty: 20,
  twentyone: 21,
  twentytwo: 22,
  twentythree: 23,
  twentyfour: 24,
  twentyfive: 25,
};

function parseDate(value) {
  return new Date(`${value}T12:00:00`);
}

function yearOf(item) {
  return Number(item.eventDate.slice(0, 4));
}

function normalizeSpaces(value) {
  return value.replace(/\s+/g, " ").trim();
}

function extractStartYear(item) {
  const story = item.story || "";
  const directPatterns = [
    /\bsince (\d{4})\b/i,
    /\bopened in (\d{4})\b/i,
    /\bestablished in (\d{4})\b/i,
    /\bfounded in (\d{4})\b/i,
    /\bserv(?:ed|ing).* since (\d{4})\b/i,
  ];

  for (const pattern of directPatterns) {
    const match = story.match(pattern);
    if (match) {
      return Number(match[1]);
    }
  }

  const ageDigitMatch = story.match(/\bafter (\d{1,2})\+? years\b/i)
    || story.match(/\b(?:almost|about|over) (\d{1,2}) years old\b/i)
    || story.match(/\bfor (\d{1,2}) years\b/i);
  if (ageDigitMatch) {
    return yearOf(item) - Number(ageDigitMatch[1]);
  }

  const ageWordMatch = story.match(
    /\bafter ((?:twenty|nineteen|eighteen|seventeen|sixteen|fifteen|fourteen|thirteen|twelve|eleven|ten|nine|eight|seven|six|five|four|three|two|one)(?:[- ](?:one|two|three|four|five))?) years\b/i,
  );
  if (ageWordMatch) {
    const token = ageWordMatch[1].replace(/[\s-]+/g, "").toLowerCase();
    if (NUMBER_WORDS[token]) {
      return yearOf(item) - NUMBER_WORDS[token];
    }
  }

  return null;
}

function buildRange(item) {
  const endYear = yearOf(item);
  const startYear = extractStartYear(item);

  if (item.status === "opened") {
    if (startYear && startYear <= endYear) {
      return `${startYear} - present`;
    }
    return `${endYear} - present`;
  }

  if (startYear && startYear <= endYear) {
    return `${startYear} - ${endYear}`;
  }

  return `closed ${endYear}`;
}

function buildDescription(item) {
  let story = normalizeSpaces(item.story || "");

  if (story.startsWith("Automatically verified from the lead pipeline.")) {
    const statusPhrase = item.status === "closed" ? "Closed" : "Opened";
    const area = item.neighborhood || "the metro";
    const type = item.cuisine && item.cuisine !== "Category Pending"
      ? item.cuisine
      : item.venueTypeLabel.toLowerCase();
    const verification =
      item.verificationLevel === "verified"
        ? "Local coverage confirmed the event."
        : "Still needs stronger sourcing.";
    return `${statusPhrase} in ${item.dateLabel}, ${item.name} was tracked as a ${type} in ${area}. ${verification}`;
  }

  story = story
    .replace(/^Known for\s+/i, "Known for ")
    .replace(/\s+/g, " ")
    .trim();

  if (story.length > 180) {
    const clipped = story.slice(0, 177);
    return `${clipped.slice(0, clipped.lastIndexOf(" "))}...`;
  }

  return story;
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

function renderTimeline() {
  const items = filteredItems();
  resultsCountEl.textContent = `${items.length} result${items.length === 1 ? "" : "s"}`;
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
    const article = fragment.querySelector(".tile-card");
    const statusBadge = fragment.querySelector('[data-field="status"]');
    const verificationBadge = fragment.querySelector('[data-field="verification"]');

    fragment.querySelector('[data-field="range"]').textContent = buildRange(item);
    fragment.querySelector('[data-field="type"]').textContent = item.venueTypeLabel;
    fragment.querySelector('[data-field="name"]').textContent = item.name;
    fragment.querySelector('[data-field="description"]').textContent = buildDescription(item);

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
