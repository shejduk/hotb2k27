// Registry of tabs. The menu and the router are built from this list.
//
// To add a feature: create a file in js/views/ that exports
//   render(container)  -> optionally returns a cleanup function
// and add one entry below. Nothing else needs to change.
//
// icon is the "d" attribute of a 24x24 SVG path.

export const modules = [
  {
    id: "dashboard",
    title: "Dashboard",
    icon: "M4 4h7v7H4zM13 4h7v4h-7zM13 11h7v9h-7zM4 14h7v6H4z",
    view: () => import("./views/dashboard.js"),
  },
  {
    id: "history",
    title: "History",
    icon: "M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    view: () => import("./views/history.js"),
  },
  {
    id: "settings",
    title: "Settings",
    icon: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
    view: () => import("./views/settings.js"),
  },
  {
    id: "extensions",
    title: "Extensions",
    icon: "M12 5v14M5 12h14",
    view: () => import("./views/extensions.js"),
  },
];
