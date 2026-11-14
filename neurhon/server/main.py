"""Starts the UI server. Run with `neurhon-ui` or `python -m neurhon.server.main`."""

import argparse
import threading
import webbrowser

import uvicorn

from neurhon.server.app import create_app
from neurhon.server.config import HISTORY_PATH
from neurhon.server.history_jsonl import JsonlHistoryStore
from neurhon.server.mocks import MockMoodProvider, MockMusicController
from neurhon.server.notify import create_notifier


def main() -> None:
    parser = argparse.ArgumentParser(description="neurhon UI server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args()

    # This is the one place that chooses the implementations.
    # Teammates replace the mocks below with the real EEG and Spotify classes.
    mood = MockMoodProvider()
    music = MockMusicController()
    history = JsonlHistoryStore(HISTORY_PATH)

    # powiadomienia systemowe to dodatek: gdy ich nie ma, działa sam baner w aplikacji
    app = create_app(mood, music, history, notifier=create_notifier())

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    print(f"neurhon UI on {url}  (Ctrl+C to stop)")

    # 127.0.0.1 keeps the server reachable only from this computer.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
