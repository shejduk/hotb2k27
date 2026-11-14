// Shared app state. Views subscribe and redraw when it changes.

import { api, openMoodSocket } from "./api.js";

const SETTINGS_KEY = "neurhon.ui.settings";
const DEFAULT_COLOR = "#4f8cff";
const NEUTRAL_ACCENT = "#f2f2f0";

// Na razie UI jest monochromatyczne. Zmień na true, żeby wrócić do kolorów nastrojów z config.py.
export const USE_MOOD_COLORS = false;

// ---- settings kept in this browser only ----

const defaults = { pauseInBackground: true };

function loadSettings() {
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}") };
  } catch {
    return { ...defaults };
  }
}

export const settings = loadSettings();

export function saveSettings(patch) {
  Object.assign(settings, patch);
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // storage can be blocked; the setting then lasts until the page closes
  }
}

// ---- live state ----

export const state = {
  config: { metrics: [], moods: [] },
  status: null,
  mood: null,
  player: null,
  auto: false,
  break: { enabled: false, phase: "off", threshold: 0.3, ends_at: null },
  live: false,
};

const listeners = new Set();
let pending = false;

/** True while the window is hidden and the user asked us not to redraw. */
export function isPaused() {
  return settings.pauseInBackground && document.hidden;
}

export function moodMeta(label) {
  return state.config.moods.find((m) => m.id === label) || null;
}

/** Kolor nastroju, albo null, gdy kolory są wyłączone. */
export function moodColor(label) {
  return USE_MOOD_COLORS ? moodMeta(label)?.color || DEFAULT_COLOR : null;
}

function applyAccent() {
  const color = moodColor(state.mood?.label) || NEUTRAL_ACCENT;
  document.documentElement.style.setProperty("--mood", color);
}

function notify() {
  if (isPaused()) {
    pending = true;
    return;
  }
  pending = false;
  applyAccent();
  listeners.forEach((fn) => fn(state));
}

/** Calls fn now and again on every change. Returns an unsubscribe function. */
export function subscribe(fn) {
  listeners.add(fn);
  fn(state);
  return () => listeners.delete(fn);
}

function applySnapshot(message) {
  state.mood = message.mood;
  state.player = message.player;
  state.auto = message.auto;
  if (message.break) state.break = message.break;

  notify();
}

export function setPlayer(player) {
  state.player = player;
  notify();
}

export function setAuto(auto) {
  state.auto = auto;
  notify();
}

export function setBreak(breakState) {
  state.break = breakState;
  notify();
}

export function redraw() {
  notify();
}

export async function initState() {
  try {
    const [config, status] = await Promise.all([api.config(), api.status()]);
    state.config = config;
    state.status = status;
    state.auto = status.auto;
  } catch (error) {
    console.error("Could not load config and status", error);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && pending) notify();
  });

  openMoodSocket({
    onMessage: applySnapshot,
    onOpen: () => {
      state.live = true;
      notify();
    },
    onClose: () => {
      state.live = false;
      notify();
    },
  });
}
