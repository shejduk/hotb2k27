// Tryb przerwy w interfejsie: baner z propozycją i nakładka na czas przerwy.
// Działa na każdej zakładce, bo jest montowany w app.js, a nie w widoku.

import { api } from "./api.js";
import { h, toast } from "./dom.js";
import { setBreak, state, subscribe } from "./state.js";

async function act(request, errorMessage) {
  try {
    setBreak(await request());
  } catch {
    toast(errorMessage);
  }
}

function formatTime(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function mountBreak(parent) {
  // ---- propozycja przerwy (faza "offer") ----
  const offerText = h("p", { class: "break-offer-text" });
  const offer = h(
    "div",
    { class: "break-offer", role: "alert" },
    h("strong", null, "Your focus dropped"),
    offerText,
    h(
      "div",
      { class: "controls" },
      h(
        "button",
        { class: "btn btn-primary", type: "button", onclick: () => act(api.acceptBreak, "Could not start the break.") },
        "Stop music"
      ),
      h("button", { class: "btn", type: "button", onclick: () => act(api.dismissBreak, "Could not dismiss.") }, "Not now")
    )
  );

  // ---- przerwa trwa (faza "active") ----
  const countdown = h("p", { class: "break-countdown", "aria-live": "off" }, "10:00");
  const overlay = h(
    "div",
    { class: "break-overlay", role: "dialog", "aria-modal": "true", "aria-label": "Break" },
    h(
      "div",
      { class: "break-overlay-inner" },
      h("h2", { class: "page-title" }, "Time for a break"),
      countdown,
      h("p", { class: "page-sub" }, "Step away from the screen. Mood tracking is paused."),
      h(
        "button",
        { class: "btn", type: "button", onclick: () => act(api.endBreak, "Could not end the break.") },
        "End break now"
      )
    )
  );

  parent.append(offer, overlay);

  let timer = null;

  function tick() {
    const left = state.break.ends_at ? state.break.ends_at - Date.now() / 1000 : 0;
    countdown.textContent = formatTime(left);
  }

  subscribe((st) => {
    const phase = st.break.phase;

    offer.classList.toggle("is-open", phase === "offer"); // ukrywanie robi CSS (visibility), z animacją
    const song = st.player?.track?.title;
    offerText.textContent = `${song ? `"${song}"` : "Loud music"} is playing until you decide. Stopping the music starts a 10 minute break.`;

    overlay.classList.toggle("is-open", phase === "active");
    if (phase === "active" && !timer) {
      tick();
      timer = setInterval(tick, 500);
    } else if (phase !== "active" && timer) {
      clearInterval(timer);
      timer = null;
    }
  });
}
