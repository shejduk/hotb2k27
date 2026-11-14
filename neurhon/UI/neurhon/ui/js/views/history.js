// History: every song change with the mood that caused it.

import { api } from "../api.js";
import { capitalize, h } from "../dom.js";
import { isPaused, moodColor, moodMeta, state } from "../state.js";

const RANGES = [
  { id: "all", title: "All time" },
  { id: "today", title: "Today" },
  { id: "hour", title: "Last hour" },
];

const REASONS = [
  { id: "all", title: "All reasons" },
  { id: "auto", title: "Automatic" },
  { id: "manual", title: "Manual" },
];

function sinceFor(rangeId) {
  if (rangeId === "hour") return Date.now() / 1000 - 3600;
  if (rangeId === "today") {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return start.getTime() / 1000;
  }
  return undefined;
}

const isAuto = (entry) => (entry.reason || "").startsWith("auto");

function reasonText(reason) {
  const text = reason || "";
  return text.startsWith("auto") ? text.replace(/^auto:\s*/, "Automatic: ") : capitalize(text);
}

function dayLabel(date) {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

function select(options, label) {
  return h(
    "select",
    { class: "field", "aria-label": label },
    options.map((o) => h("option", { value: o.id }, o.title))
  );
}

export function render(root) {
  const rangeSelect = select(RANGES, "Time range");
  const moodSelect = select([{ id: "all", title: "All moods" }, ...state.config.moods], "Mood");
  const reasonSelect = select(REASONS, "Reason");
  const summary = h("p", { class: "hint" });
  const listBox = h("div");
  let entries = [];

  function emptyState(title, text) {
    return h(
      "div",
      { class: "empty" },
      h("strong", null, title),
      text,
      " ",
      h("a", { href: "#dashboard" }, "Go to Dashboard")
    );
  }

  function row(entry) {
    const meta = moodMeta(entry.mood.label);
    const time = new Date(entry.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return h(
      "li",
      { class: "history-item" },
      h("span", { class: "history-time" }, time),
      h("div", { class: "history-track" }, h("strong", null, entry.track.title), h("span", null, `${entry.track.artist}${entry.track.playlist ? `, ${entry.track.playlist}` : ""}`)),
      h("span", { class: "chip" }, h("i", { style: moodColor(entry.mood.label) ? `background:${moodColor(entry.mood.label)}` : null }), meta?.title ?? capitalize(entry.mood.label)),
      h("span", { class: "history-reason" }, reasonText(entry.reason))
    );
  }

  function draw() {
    const filtered = entries.filter((e) => {
      if (moodSelect.value !== "all" && e.mood.label !== moodSelect.value) return false;
      if (reasonSelect.value === "auto" && !isAuto(e)) return false;
      if (reasonSelect.value === "manual" && isAuto(e)) return false;
      return true;
    });

    summary.textContent = `${filtered.length} song ${filtered.length === 1 ? "change" : "changes"}`;

    if (!filtered.length) {
      listBox.replaceChildren(
        entries.length
          ? emptyState("Nothing matches these filters", "Try a wider time range or another mood.")
          : emptyState("No song changes yet", "Press play on the Dashboard and skip a song, and it will show up here.")
      );
      return;
    }

    const groups = new Map();
    for (const entry of filtered) {
      const label = dayLabel(new Date(entry.timestamp * 1000));
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(entry);
    }

    listBox.replaceChildren(
      ...[...groups].flatMap(([label, items]) => [
        h("h2", { class: "day-heading" }, label),
        h("ul", { class: "history-list" }, items.map(row)),
      ])
    );
  }

  async function load() {
    try {
      entries = await api.history({ since: sinceFor(rangeSelect.value) });
      draw();
    } catch {
      summary.textContent = "";
      listBox.replaceChildren(emptyState("History could not load", "The server did not answer. Check that neurhon-ui is still running."));
    }
  }

  rangeSelect.addEventListener("change", load);
  moodSelect.addEventListener("change", draw);
  reasonSelect.addEventListener("change", draw);

  root.append(
    h("h1", { class: "page-title" }, "History"),
    h("p", { class: "page-sub" }, "Every time the song changed, with the mood you were in and why it changed."),
    h("div", { class: "filters" }, rangeSelect, moodSelect, reasonSelect),
    summary,
    listBox
  );

  load();
  const timer = setInterval(() => {
    if (!isPaused()) load();
  }, 10000);
  return () => clearInterval(timer);
}
