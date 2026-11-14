// Entry point: builds the menu, starts the live state and switches views by URL hash.

import { mountBreak } from "./break.js";
import { h, icon } from "./dom.js";
import { modules } from "./modules.js";
import { initState, subscribe } from "./state.js";

const nav = document.getElementById("nav");
const view = document.getElementById("view");
const railStatus = document.getElementById("rail-status");

let cleanup = null;
let routeToken = 0;

function buildNav() {
  nav.replaceChildren(
    ...modules.map((m) =>
      h("a", { href: `#${m.id}`, "data-id": m.id }, icon(m.icon), h("span", null, m.title))
    )
  );
}

function markCurrent(id) {
  for (const link of nav.querySelectorAll("a")) {
    if (link.dataset.id === id) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

async function route() {
  const id = location.hash.slice(1) || modules[0].id;
  const module = modules.find((m) => m.id === id) || modules[0];
  const token = ++routeToken;

  markCurrent(module.id);
  cleanup?.();
  cleanup = null;
  view.replaceChildren();

  try {
    const loaded = await module.view();
    if (token !== routeToken) return; // user already moved on
    cleanup = loaded.render(view) || null;
  } catch (error) {
    console.error(error);
    view.replaceChildren(
      h("div", { class: "empty" }, h("strong", null, "This tab could not load"), String(error.message || error))
    );
  }
  window.scrollTo(0, 0);
}

function drawRailStatus(state) {
  const status = state.status;
  const spotify = status?.spotify;
  railStatus.replaceChildren(
    h(
      "div",
      { class: "status-line" },
      h("span", { class: `dot ${state.live ? "on" : "off"}` }),
      state.live ? "Live" : "Offline, reconnecting"
    ),
    h("div", null, status ? `Mood from ${status.mood_source}` : "Waiting for server"),
    h("div", null, spotify ? (spotify.connected ? "Spotify connected" : "Spotify not connected") : "")
  );
}

async function boot() {
  buildNav();
  await initState();
  subscribe(drawRailStatus);
  mountBreak(document.body);
  window.addEventListener("hashchange", route);
  route();
}

boot();
