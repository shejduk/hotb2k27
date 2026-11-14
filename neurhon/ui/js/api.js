// The only file that talks to the server. Everything else calls these functions.

async function request(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(`${method} ${url} failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  config: () => request("GET", "/api/config"),
  status: () => request("GET", "/api/status"),
  player: () => request("GET", "/api/player"),
  play: () => request("POST", "/api/player/play"),
  pause: () => request("POST", "/api/player/pause"),
  next: () => request("POST", "/api/player/next"),
  setAuto: (enabled) => request("POST", "/api/auto", { enabled }),
  history: ({ limit = 200, since } = {}) => {
    const params = new URLSearchParams({ limit });
    if (since != null) params.set("since", since);
    return request("GET", `/api/history?${params}`);
  },
  setBreakEnabled: (enabled) => request("POST", "/api/break/enabled", { enabled }),
  acceptBreak: () => request("POST", "/api/break/accept"),
  dismissBreak: () => request("POST", "/api/break/dismiss"),
  endBreak: () => request("POST", "/api/break/end"),
  testBreak: () => request("POST", "/api/break/test"),
  setBreakThreshold: (value) => request("PUT", "/api/break/threshold", { value }),
  mappings: () => request("GET", "/api/mappings"),
  saveMappings: (mappings) => request("PUT", "/api/mappings", { mappings }),
};

/** Live mood stream. Reconnects by itself. Returns a function that closes it. */
export function openMoodSocket({ onMessage, onOpen, onClose }) {
  let socket;
  let closedByUs = false;
  let retryTimer;

  const connect = () => {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/ws/mood`);
    socket.onopen = () => onOpen?.();
    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch (error) {
        console.error("Bad mood message", error);
      }
    };
    socket.onclose = () => {
      onClose?.();
      if (!closedByUs) retryTimer = setTimeout(connect, 2000);
    };
  };

  connect();
  return () => {
    closedByUs = true;
    clearTimeout(retryTimer);
    socket?.close();
  };
}
