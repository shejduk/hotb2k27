"""The web server: connects the UI to the mood, music and history modules."""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from neurhon.server.break_flow import BreakFlow
from neurhon.server.break_mode import BreakMonitor
from neurhon.server.config import (
    BREAK_COOLDOWN_MINUTES,
    BREAK_GRACE_MINUTES,
    BREAK_MINUTES,
    DATA_DIR,
    FOCUS_THRESHOLD_DEFAULT,
    LOW_FOCUS_SECONDS,
    METRICS,
    MOOD_LABELS,
    WAKE_TRACKS,
    WAKE_VOLUME,
    get_setting,
)
from neurhon.server.interfaces import (
    HistoryEntry,
    HistoryStore,
    MoodProvider,
    MusicController,
)
from neurhon.server.notify import NullNotifier

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
TICK_SECONDS = 1.0  # how often the mood is read and pushed to the UI


class AutoBody(BaseModel):
    enabled: bool


class MappingsBody(BaseModel):
    mappings: dict[str, str]


class EnabledBody(BaseModel):
    enabled: bool


class ThresholdBody(BaseModel):
    value: float = Field(ge=0.0, le=1.0)  # próg focusu, 0..1


def create_app(
    mood: MoodProvider,
    music: MusicController,
    history: HistoryStore,
    data_dir: Path = DATA_DIR,
    notifier=None,
) -> FastAPI:
    """Build the app. It only knows the interfaces, never the real implementations."""

    state = {"auto": False, "mood": None}
    clients: set[WebSocket] = set()
    mappings_path = data_dir / "mappings.json"
    settings_path = data_dir / "settings.json"

    def load_settings() -> dict:
        try:
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_settings(patch: dict) -> None:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({**load_settings(), **patch}, indent=2), encoding="utf-8"
        )

    breaker = BreakMonitor(
        threshold=load_settings().get("focus_threshold", FOCUS_THRESHOLD_DEFAULT),
        low_seconds=LOW_FOCUS_SECONDS,
        break_seconds=BREAK_MINUTES * 60,
        cooldown_seconds=BREAK_COOLDOWN_MINUTES * 60,
        grace_seconds=BREAK_GRACE_MINUTES * 60,
    )

    def latest_mood():
        return state["mood"] or mood.get_mood()

    def player_state() -> dict:
        track = music.now_playing()
        return {
            "track": asdict(track) if track else None,
            "playing": music.is_playing(),
        }

    def snapshot() -> dict:
        return {
            "mood": asdict(latest_mood()),
            "player": player_state(),
            "auto": state["auto"],
            "break": flow.snapshot(),
        }

    def log_change(reason: str) -> None:
        track = music.now_playing()
        if track:
            history.append(HistoryEntry(time.time(), track, latest_mood(), reason))

    def on_wake_started(focus) -> None:
        reason = f"break: low focus ({focus:.2f})" if focus is not None else "break: test"
        log_change(reason)

    # BreakFlow łączy tryb przerwy z muzyką i powiadomieniami (patrz break_flow.py)
    flow = BreakFlow(
        breaker, music, notifier or NullNotifier(), WAKE_TRACKS, WAKE_VOLUME, on_wake_started=on_wake_started
    )

    def step() -> None:
        """Read the mood once. In auto mode, skip to a new song when the label changes.

        PLACEHOLDER: choosing the music from the mood is the Spotify side's job.
        Here the next song of the mock playlist stands in for that choice.
        """
        if flow.suspended:
            flow.tick(None)  # przerwa trwa: tylko pilnujemy, czy minął czas
            return  # program jest zawieszony: bez odczytu nastroju, muzyki i historii

        previous = state["mood"]
        current = mood.get_mood()
        state["mood"] = current

        flow.tick(current.scores.get("focus"))  # tu może ruszyć muzyka pobudzająca
        if flow.waking:
            return  # gra muzyka pobudzająca, tryb auto jej nie zmienia

        if (
            state["auto"]
            and previous is not None
            and previous.label != current.label
            and music.is_playing()
        ):
            music.next_track()
            log_change(f"auto: mood became {current.label}")

    async def broadcast() -> None:
        message = snapshot()
        for client in list(clients):
            try:
                await client.send_json(message)
            except Exception:
                clients.discard(client)

    async def mood_loop() -> None:
        while True:
            try:
                step()
                await broadcast()
            except Exception as error:  # keep the loop alive whatever a provider does
                print(f"mood loop error: {error!r}")
            await asyncio.sleep(TICK_SECONDS)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = asyncio.create_task(mood_loop())
        yield
        task.cancel()

    app = FastAPI(title="neurhon", lifespan=lifespan)

    def load_mappings() -> dict[str, str]:
        try:
            return json.loads(mappings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @app.get("/api/mood")
    def get_mood():
        return asdict(latest_mood())

    @app.get("/api/player")
    def get_player():
        return player_state()

    @app.post("/api/player/play")
    def play():
        music.play()
        return player_state()

    @app.post("/api/player/pause")
    def pause():
        music.pause()
        return player_state()

    @app.post("/api/player/next")
    def next_track():
        music.next_track()
        log_change("manual skip")
        return player_state()

    @app.get("/api/history")
    def get_history(limit: int = 100, since: float | None = None):
        return [asdict(entry) for entry in history.get_entries(limit, since)]

    @app.get("/api/config")
    def get_config():
        return {
            "metrics": [asdict(metric) for metric in METRICS],
            "moods": [asdict(label) for label in MOOD_LABELS],
        }

    @app.get("/api/status")
    def get_status():
        return {
            "mood_source": type(mood).__name__,
            "music_source": type(music).__name__,
            "auto": state["auto"],
            # "connected" stays False until the Spotify side implements the login.
            "spotify": {
                "configured": bool(get_setting("SPOTIFY_CLIENT_ID")),
                "connected": False,
            },
        }

    @app.post("/api/auto")
    def set_auto(body: AutoBody):
        state["auto"] = body.enabled
        return {"auto": state["auto"]}

    @app.post("/api/break/enabled")
    def set_break_enabled(body: EnabledBody):
        flow.set_enabled(body.enabled)
        return flow.snapshot()

    @app.post("/api/break/accept")
    def accept_break():
        flow.accept()  # "Stop music": cisza i początek przerwy
        return flow.snapshot()

    @app.post("/api/break/dismiss")
    def dismiss_break():
        flow.dismiss()  # "Not now": poprzednia muzyka wraca, 10 minut spokoju
        return flow.snapshot()

    @app.post("/api/break/end")
    def end_break():
        flow.end()
        return flow.snapshot()

    @app.post("/api/break/test")
    def test_break():
        flow.test()  # cała sekwencja bez czekania na spadek focusu
        return flow.snapshot()

    @app.put("/api/break/threshold")
    def set_break_threshold(body: ThresholdBody):
        breaker.threshold = body.value
        save_settings({"focus_threshold": body.value})
        return flow.snapshot()

    @app.get("/api/mappings")
    def get_mappings():
        return load_mappings()

    @app.put("/api/mappings")
    def put_mappings(body: MappingsBody):
        mappings_path.parent.mkdir(parents=True, exist_ok=True)
        mappings_path.write_text(
            json.dumps(body.mappings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return body.mappings

    @app.websocket("/ws/mood")
    async def mood_socket(websocket: WebSocket):
        await websocket.accept()
        clients.add(websocket)
        try:
            await websocket.send_json(snapshot())
            while True:
                await websocket.receive_text()  # we only wait for the client to leave
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(websocket)

    # Mounted last, so the /api and /ws routes above take priority.
    if UI_DIR.exists():
        app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")

    return app
