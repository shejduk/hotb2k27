// Tiny helpers for building DOM without a framework.

const SVG_NS = "http://www.w3.org/2000/svg";

function applyAttrs(el, attrs) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.setAttribute("class", value);
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
}

function appendChildren(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
}

/** h("div", {class: "card"}, "text", otherElement) -> <div class="card">...</div> */
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  applyAttrs(el, attrs);
  appendChildren(el, children);
  return el;
}

/** Same as h() but for SVG elements. */
export function s(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  applyAttrs(el, attrs);
  appendChildren(el, children);
  return el;
}

/** A 24x24 icon from one path definition. Outlined by default, solid when filled is true. */
export function icon(pathData, filled = false) {
  return s(
    "svg",
    { viewBox: "0 0 24 24", fill: filled ? "currentColor" : "none", stroke: "currentColor", "stroke-width": filled ? "1.8" : "2.2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    s("path", { d: pathData })
  );
}

/** Short message in the corner of the screen. */
export function toast(message) {
  const box = document.getElementById("toasts");
  if (!box) return;
  const el = h("div", { class: "toast", role: "status" }, message);
  box.append(el);
  setTimeout(() => el.remove(), 4000);
}

export function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}
