// Extensions: placeholder for features added later, and a guide on how to add one.

import { h } from "../dom.js";
import { modules } from "../modules.js";

export function render(root) {
  root.append(
    h("h1", { class: "page-title" }, "Extensions"),
    h("p", { class: "page-sub" }, "Room for features that are not built yet."),
    h(
      "div",
      { class: "stack" },
      h(
        "div",
        { class: "empty" },
        h("strong", null, "No extensions yet"),
        "A new tab takes one file and one line."
      ),
      h(
        "section",
        { class: "card" },
        h("h2", { class: "card-title" }, "How to add a tab"),
        h(
          "ol",
          { style: "margin:0;padding-left:1.2em;display:grid;gap:6px" },
          h("li", null, "Create ", h("code", null, "neurhon/ui/js/views/my_feature.js"), " that exports ", h("code", null, "render(container)"), "."),
          h("li", null, "Add an entry to ", h("code", null, "neurhon/ui/js/modules.js"), ". The menu updates by itself.")
        )
      ),
      h(
        "section",
        { class: "card" },
        h("h2", { class: "card-title" }, "Registered tabs"),
        h("dl", { class: "kv" }, modules.flatMap((m) => [h("dt", null, m.id), h("dd", null, m.title)]))
      )
    )
  );
}
