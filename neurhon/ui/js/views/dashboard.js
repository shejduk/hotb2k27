// Dashboard: where you are on the mood map, what is playing, and the player controls.

import { api } from "../api.js";
import { capitalize, h, icon, s, toast } from "../dom.js";
import { moodMeta, setPlayer, state, subscribe } from "../state.js";

// Drawing area of the mood map (SVG units).
const W = 460;
const H = 430;
const PX = 44;
const PY = 16;
const PW = 400;
const PH = 380;
const xOf = (valence) => PX + valence * PW;
const yOf = (energy) => PY + (1 - energy) * PH;

const PLAY = "M9 5v14l11-7z";
const PAUSE = "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z";
const NEXT = "M6 5l9 7-9 7zM18 5v14";

function sideLabel(text, x, y, anchor, rotate) {
  return s(
    "text",
    {
      class: "plane-text",
      x,
      y,
      "text-anchor": anchor,
      transform: rotate ? `rotate(-90 ${x} ${y})` : null,
    },
    text
  );
}

function restart(element, className) {
  element.classList.remove(className);
  void element.getBoundingClientRect(); // wymusza ponowne odtworzenie animacji
  element.classList.add(className);
}

function buildPlane() {
  const midX = xOf(0.5);
  const midY = yOf(0.5);

  const ripple = s("circle", { class: "plane-ripple", r: 9 });
  const dot = s(
    "g",
    { class: "plane-dot" },
    ripple,
    s("circle", { class: "halo", r: 22 }),
    s("circle", { class: "core", r: 9 })
  );
  // podpis aktualnego nastroju jedzie razem z kropką
  const label = s("text", { class: "plane-dot-label", x: 18, y: 4 }, "");
  const pointer = s("g", { class: "plane-pointer" }, dot, label);
  pointer.style.transform = `translate(${midX}px, ${midY}px)`;

  const svg = s(
    "svg",
    { class: "plane", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Mood map: energy against valence" },
    s("rect", { class: "plane-bg", x: PX, y: PY, width: PW, height: PH, rx: 14 }),
    s("line", { class: "plane-axis", x1: midX, y1: PY, x2: midX, y2: PY + PH }),
    s("line", { class: "plane-axis", x1: PX, y1: midY, x2: PX + PW, y2: midY }),
    sideLabel("Unpleasant", PX, PY + PH + 22, "start"),
    sideLabel("Valence", midX, PY + PH + 22, "middle"),
    sideLabel("Pleasant", PX + PW, PY + PH + 22, "end"),
    sideLabel("Low energy", 16, PY + PH, "start", true),
    sideLabel("Energy", 16, midY, "middle", true),
    sideLabel("High energy", 16, PY, "end", true),
    pointer
  );

  return {
    svg,
    move(energy, valence) {
      pointer.style.transform = `translate(${xOf(valence)}px, ${yOf(energy)}px)`;
      // blisko prawej krawędzi podpis ląduje po lewej stronie kropki
      const flip = valence > 0.72;
      label.setAttribute("x", flip ? -18 : 18);
      label.setAttribute("text-anchor", flip ? "end" : "start");
    },
    setLabel(text) {
      label.textContent = text;
    },
    /** Fala wokół kropki przy zmianie nastroju. */
    ping() {
      restart(ripple, "is-pinging");
    },
  };
}

async function togglePlay() {
  try {
    setPlayer(await (state.player?.playing ? api.pause() : api.play()));
  } catch {
    toast("Could not reach the server.");
  }
}

async function skip() {
  try {
    setPlayer(await api.next());
  } catch {
    toast("Could not reach the server.");
  }
}

let entered = false; // wejście kart odtwarzamy tylko przy pierwszym otwarciu widoku

function cardAttrs(index) {
  return entered ? { class: "card" } : { class: "card enter", style: `--i:${index}` };
}

export function render(root) {
  const plane = buildPlane();
  let shownLabel = null; // nastrój, który widać w dużym napisie

  const notice = h(
    "div",
    { class: "notice", hidden: true },
    "Showing demo data. No headband or Spotify is connected yet."
  );
  const moodTitle = h("h1", { class: "mood-title" }, "Waiting for data");
  const moodSub = h("p", { class: "mood-sub" }, "Connecting to the server.");

  const playlist = h("p", { class: "now-playlist" });
  const trackTitle = h("p", { class: "now-title" }, "Nothing loaded");
  const artist = h("p", { class: "now-artist" });
  const playIcon = icon(PLAY, true);
  const pauseIcon = icon(PAUSE, true);
  const playButton = h(
    "button",
    { class: "btn btn-primary btn-round", type: "button", onclick: togglePlay },
    h("span", { class: "icon-swap" }, playIcon, pauseIcon)
  );
  const nextButton = h(
    "button",
    { class: "btn btn-round", type: "button", "aria-label": "Next track", onclick: skip },
    icon(NEXT, true)
  );

  const metricsBox = h("div");
  const meterRows = new Map();

  function meterFor(key, title, description) {
    if (!meterRows.has(key)) {
      const value = h("span", { class: "meter-value" });
      const bar = h("span");
      const marker = h("i", { class: "meter-threshold", hidden: true, title: "Break threshold" });
      const row = h(
        "div",
        { class: "meter-row", title: description || null },
        h("div", { class: "meter-head" }, h("span", null, title), value),
        h("div", { class: "meter" }, bar, marker)
      );
      metricsBox.append(row);
      meterRows.set(key, { value, bar, marker });
    }
    return meterRows.get(key);
  }

  function showMoodTitle(text, label) {
    if (shownLabel === null) {
      moodTitle.textContent = text; // pierwszy napis: bez animacji
    } else if (label !== shownLabel) {
      plane.ping();
      moodTitle.classList.add("is-out");
      setTimeout(() => {
        moodTitle.textContent = text;
        moodTitle.classList.remove("is-out");
        restart(moodTitle, "is-in");
      }, 150);
    }
    shownLabel = label;
  }

  function update(st) {
    const mood = st.mood;
    notice.hidden = !st.status?.mood_source?.startsWith("Mock");

    if (mood) {
      const meta = moodMeta(mood.label);
      const title = meta?.title ?? capitalize(mood.label);
      showMoodTitle(title, mood.label);
      plane.setLabel(title);
      moodSub.textContent = `Reading from ${new Date(mood.timestamp * 1000).toLocaleTimeString()}`;

      const scores = mood.scores || {};
      plane.move(scores.energy ?? 0.5, scores.valence ?? 0.5);

      const known = st.config.metrics.map((m) => m.id);
      const extra = Object.keys(scores).filter((key) => !known.includes(key));
      const list = [...st.config.metrics, ...extra.map((id) => ({ id, title: capitalize(id) }))];
      for (const metric of list) {
        if (scores[metric.id] == null) continue;
        const row = meterFor(metric.id, metric.title, metric.description);
        row.value.textContent = scores[metric.id].toFixed(2);
        row.bar.style.width = `${Math.round(scores[metric.id] * 100)}%`;

        if (metric.id === "focus") {
          // znacznik progu przerwy na pasku Focus
          row.marker.hidden = !st.break.enabled;
          row.marker.style.left = `${Math.round(st.break.threshold * 100)}%`;
        }
      }
    }

    const player = st.player;
    playlist.textContent = player?.track?.playlist || "No playlist";
    trackTitle.textContent = player?.track?.title ?? "Nothing loaded";
    artist.textContent = player?.track?.artist ?? "";
    playIcon.setAttribute("data-active", String(!player?.playing));
    pauseIcon.setAttribute("data-active", String(Boolean(player?.playing)));
    playButton.setAttribute("aria-label", player?.playing ? "Pause" : "Play");
  }

  root.append(
    notice,
    h(
      "div",
      { class: "dash" },
      h("section", cardAttrs(0), moodTitle, moodSub, plane.svg),
      h(
        "div",
        { class: "dash-side" },
        h(
          "section",
          cardAttrs(1),
          h("h2", { class: "card-title" }, "Now playing"),
          playlist,
          trackTitle,
          artist,
          h("div", { class: "controls" }, playButton, nextButton)
        ),
        h("section", cardAttrs(2), h("h2", { class: "card-title" }, "Signals"), metricsBox)
      )
    )
  );

  entered = true;
  return subscribe(update);
}
