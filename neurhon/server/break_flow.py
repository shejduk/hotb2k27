"""Przebieg trybu przerwy: łączy BreakMonitor (kiedy) z muzyką i powiadomieniami (co robimy).

BreakMonitor zna tylko fazy i czas. Tu dzieje się reszta:
  * faza budzenia: zapamiętujemy, co grało, puszczamy głośną muzykę w pętli i pokazujemy push,
  * "Not now": wracamy do poprzedniej muzyki, 10 minut spokoju,
  * "Stop music": zaczyna się przerwa (cisza), a po niej wracamy do poprzedniej muzyki.

Metody są wołane z trzech miejsc naraz: z pętli serwera (tick), z endpointów FastAPI
i z wątku powiadomień systemowych. Dlatego wszystko jest pod jedną blokadą.
"""

import random
import threading

from neurhon.server.break_mode import (
    ACTIVE,
    EVENT_BREAK_ENDED,
    EVENT_OFFER,
    OFF,
    OFFER,
    BreakMonitor,
)
from neurhon.server.interfaces import MusicController, Track


class BreakFlow:
    def __init__(
        self,
        monitor: BreakMonitor,
        music: MusicController,
        notifier,
        wake_tracks: list[Track],
        wake_volume: int,
        on_wake_started=None,
        choose=random.choice,
    ):
        self.monitor = monitor
        self._music = music
        self._notifier = notifier
        self._wake_tracks = wake_tracks
        self._wake_volume = wake_volume
        self._on_wake_started = on_wake_started  # np. zapis do historii: funkcja(focus)
        self._choose = choose
        self._lock = threading.RLock()
        self._saved = None  # stan odtwarzacza sprzed muzyki pobudzającej

    # ---- co widzi reszta serwera ----

    @property
    def phase(self) -> str:
        return self.monitor.phase

    @property
    def suspended(self) -> bool:
        """Trwa przerwa: serwer nie czyta nastroju, nie zmienia muzyki i nie pisze historii."""
        return self.monitor.phase == ACTIVE

    @property
    def waking(self) -> bool:
        """Gra muzyka pobudzająca i czekamy na decyzję użytkownika."""
        return self.monitor.phase == OFFER

    def snapshot(self) -> dict:
        return self.monitor.snapshot()

    # ---- wołane co sekundę przez serwer ----

    def tick(self, focus: float | None) -> None:
        """Podaj aktualny focus (w trakcie przerwy może być None)."""
        with self._lock:
            event = self.monitor.update(focus)
            if event == EVENT_OFFER:
                self._start_wake(focus)
            elif event == EVENT_BREAK_ENDED:
                self._restore(resume=True)  # przerwa skończyła się sama: wracamy do dawnej muzyki
                self._notify("show_break_over")

    # ---- decyzje użytkownika (przyciski na stronie albo w powiadomieniu) ----

    def accept(self) -> bool:
        """"Stop music": muzyka pobudzająca się kończy i zaczyna się przerwa."""
        with self._lock:
            if not self.monitor.accept():
                return False
            self._notify("close_offer")
            self._restore(resume=False, keep=True)  # głośność wraca, muzyka milczy; stan zostaje na koniec przerwy
            return True

    def dismiss(self) -> bool:
        """"Not now": wracamy do poprzedniej muzyki i przez 10 minut focus nie jest mierzony."""
        with self._lock:
            if not self.monitor.dismiss():
                return False
            self._notify("close_offer")
            self._restore(resume=True)
            return True

    def end(self) -> bool:
        """"End break now": koniec przerwy na własne ryzyko, focus jest od razu mierzony."""
        with self._lock:
            if not self.monitor.end():
                return False
            self._restore(resume=True)
            return True

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            before = self.monitor.phase
            self.monitor.set_enabled(enabled)
            if not enabled and before in (OFFER, ACTIVE):
                if before == OFFER:
                    self._notify("close_offer")
                self._restore(resume=True)

    def test(self) -> bool:
        """Przycisk testowy: uruchamia całą sekwencję bez czekania na spadek focusu."""
        with self._lock:
            if self.monitor.phase == OFF:
                self.monitor.set_enabled(True)
            if self.monitor.force_offer() != EVENT_OFFER:
                return False
            self._start_wake(None)
            return True

    # ---- w środku ----

    def _start_wake(self, focus: float | None) -> None:
        try:
            self._saved = self._music.capture_state()
        except Exception as error:
            print(f"break: could not capture playback state: {error!r}")
            self._saved = None

        track = self._choose(self._wake_tracks)
        try:
            self._music.play_track(track, volume=self._wake_volume, repeat=True)
        except Exception as error:  # brak muzyki nie blokuje propozycji przerwy
            print(f"break: wake-up music failed: {error!r}")

        self._notify("show_offer", self.accept, self.dismiss, track)
        if self._on_wake_started is not None:
            try:
                self._on_wake_started(focus)
            except Exception as error:
                print(f"break: history entry failed: {error!r}")

    def _restore(self, resume: bool, keep: bool = False) -> None:
        saved = self._saved
        if not keep:
            self._saved = None
        try:
            if saved is not None:
                self._music.restore_state(saved, resume)
            else:
                self._music.pause()  # nie wiemy, co grało, więc przynajmniej gasimy muzykę pobudzającą
        except Exception as error:
            print(f"break: could not restore playback: {error!r}")

    def _notify(self, method: str, *args) -> None:
        try:
            getattr(self._notifier, method)(*args)
        except Exception as error:  # push jest dodatkiem: jego błąd nie psuje przebiegu
            print(f"break: notification {method} failed: {error!r}")
