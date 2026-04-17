const reviewListEl = document.getElementById("review-list");
const searchEl = document.getElementById("review-search");
const templateEl = document.getElementById("candidate-template");
const exportButton = document.getElementById("export-decisions");
const clearButton = document.getElementById("clear-decisions");
const toolbarNote = document.getElementById("toolbar-note");

const STORAGE_KEY = "lastCallDSMReviewDecisions";

const state = {
  candidateStatus: "all",
  decision: "all",
  search: "",
  candidates: [],
  curated: [],
  decisions: loadDecisions(),
};

function loadDecisions() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (error) {
    return {};
  }
}

function saveDecisions() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.decisions));
}

function normalize(value) {
  return (value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function setActiveChip(group, value) {
  document.querySelectorAll(`[data-filter-group="${group}"]`).forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.value === value);
  });
}

function candidateDecision(candidate) {
  return state.decisions[candidate.fingerprint] || "unreviewed";
}

function duplicateHints(candidate) {
  const guess = normalize(candidate.venue_guess || candidate.title);
  return state.curated.filter((venue) => normalize(venue.name).includes(guess) || guess.includes(normalize(venue.name)));
}

function filteredCandidates() {
  return state.candidates.filter((candidate) => {
    if (state.candidateStatus !== "all" && candidate.status_guess !== state.candidateStatus) {
      return false;
    }

    const decision = candidateDecision(candidate);
    if (state.decision !== "all" && decision !== state.decision) {
      return false;
    }

    if (!state.search) {
      return true;
    }

    const haystack = [
      candidate.title,
      candidate.summary,
      candidate.venue_guess,
      candidate.area_guess,
      candidate.source_label,
      ...(candidate.matched_terms || []),
    ]
      .join(" ")
      .toLowerCase();

    return haystack.includes(state.search.toLowerCase());
  });
}

function updateStats(candidates) {
  const duplicateCount = candidates.filter((candidate) => duplicateHints(candidate).length > 0).length;
  const reviewedCount = candidates.filter((candidate) => candidateDecision(candidate) !== "unreviewed").length;
  const highScore = candidates.reduce((max, candidate) => Math.max(max, candidate.score || 0), 0);

  document.querySelector('[data-review-stat="candidates"]').textContent = candidates.length;
  document.querySelector('[data-review-stat="high"]').textContent = highScore;
  document.querySelector('[data-review-stat="duplicates"]').textContent = duplicateCount;
  document.querySelector('[data-review-stat="reviewed"]').textContent = reviewedCount;
}

function renderLinks(container, candidate) {
  const anchor = document.createElement("a");
  anchor.href = candidate.url;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  anchor.textContent = candidate.source_label;
  container.textContent = "";
  container.append("Source: ", anchor);
  if (candidate.published_at) {
    container.append(` • Published: ${candidate.published_at}`);
  }
}

function renderHints(container, candidate, duplicates) {
  const bits = [];
  if ((candidate.matched_terms || []).length) {
    bits.push(`Matched terms: ${candidate.matched_terms.join(", ")}`);
  }
  if (duplicates.length) {
    bits.push(`Possible duplicates: ${duplicates.map((venue) => venue.name).join(" • ")}`);
  }
  container.textContent = bits.join(" | ");
}

function renderReviewList() {
  const candidates = filteredCandidates();
  updateStats(candidates);
  reviewListEl.innerHTML = "";

  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "review-empty";
    empty.textContent =
      state.candidates.length === 0
        ? "No candidate report is available yet. Run the collector to populate the queue."
        : "No candidates match the current filters.";
    reviewListEl.appendChild(empty);
    return;
  }

  candidates.forEach((candidate) => {
    const fragment = templateEl.content.cloneNode(true);
    const root = fragment.querySelector(".candidate-card");
    const duplicates = duplicateHints(candidate);
    const decision = candidateDecision(candidate);

    fragment.querySelector(".candidate-title").textContent = candidate.title;
    fragment.querySelector(".candidate-meta").textContent = [
      candidate.venue_guess || "Unknown venue",
      candidate.area_guess || "Unknown area",
      candidate.source_type || "source",
    ].join(" • ");
    fragment.querySelector(".candidate-summary").textContent = candidate.summary || "No summary available.";

    renderLinks(fragment.querySelector(".candidate-links"), candidate);
    renderHints(fragment.querySelector(".candidate-hints"), candidate, duplicates);

    const pillsEl = fragment.querySelector(".candidate-pills");
    [
      { label: candidate.status_guess, className: candidate.status_guess },
      { label: `score ${candidate.score}`, className: "score" },
      ...(duplicates.length ? [{ label: `${duplicates.length} duplicate`, className: "duplicate" }] : []),
      { label: decision, className: decision === "unreviewed" ? "review" : decision },
    ].forEach((pill) => {
      const span = document.createElement("span");
      span.className = `pill ${pill.className}`;
      span.textContent = pill.label;
      pillsEl.appendChild(span);
    });

    root.querySelectorAll("[data-decision]").forEach((button) => {
      const targetDecision = button.dataset.decision;
      button.classList.toggle("active", targetDecision === decision);
      button.addEventListener("click", () => {
        state.decisions[candidate.fingerprint] = targetDecision;
        saveDecisions();
        renderReviewList();
      });
    });

    reviewListEl.appendChild(fragment);
  });
}

async function load() {
  const [candidatePayload, curatedPayload] = await Promise.all([
    fetch("data/reports/latest-candidates.json").then((response) => (response.ok ? response.json() : [])),
    fetch("data/venues.json").then((response) => response.json()),
  ]);

  state.candidates = Array.isArray(candidatePayload) ? candidatePayload : [];
  state.curated = curatedPayload.items || [];
  toolbarNote.textContent =
    state.candidates.length > 0
      ? `Loaded ${state.candidates.length} lead candidates against ${state.curated.length} published records.`
      : "No candidate report yet. Published history is ready; run the collector to populate this queue.";

  renderReviewList();
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
  renderReviewList();
});

searchEl.addEventListener("input", (event) => {
  state.search = event.target.value.trim();
  renderReviewList();
});

exportButton.addEventListener("click", () => {
  const payload = {
    exportedAt: new Date().toISOString(),
    decisions: state.decisions,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "last-call-dsm-review-decisions.json";
  link.click();
  URL.revokeObjectURL(link.href);
});

clearButton.addEventListener("click", () => {
  state.decisions = {};
  saveDecisions();
  renderReviewList();
});

load().catch((error) => {
  toolbarNote.textContent = `Unable to load review data: ${error.message}`;
  renderReviewList();
});
