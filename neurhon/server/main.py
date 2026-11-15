import argparse
import threading
import webbrowser

import uvicorn

from neurhon.server.app import create_app
from neurhon.server.config import HISTORY_PATH
from neurhon.server.history_jsonl import JsonlHistoryStore
from neurhon.server.mocks import MockMoodProvider, MockMusicController
from neurhon.server.notify import create_notifier


def main(mood_provider=None, music=None, history=None, port=None, open_browser=None) -> None:
    """Bez argumentów startuje demo na mockach (neurhon-ui). neurhon-run podaje prawdziwe obiekty."""
    if port is None or open_browser is None:  # tryb samodzielny: flagi z linii poleceń
        parser = argparse.ArgumentParser(description="neurhon UI server")
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
        args = parser.parse_args()
        port = args.port if port is None else port
        open_browser = (not args.no_browser) if open_browser is None else open_browser

    # This is the one place that chooses the implementations.
    # Teammates replace the mocks below with the real EEG and Spotify classes.
    mood = mood_provider or MockMoodProvider()
    music = music or MockMusicController()
    history = history or JsonlHistoryStore(HISTORY_PATH)

    app = create_app(mood, music, history, notifier=create_notifier())

    url = f"http://127.0.0.1:{port}"
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    print(f"neurhon UI on {url}  (Ctrl+C to stop)")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
