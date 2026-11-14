"""Tryb przerwy: pilnuje focusu i prowadzi użytkownika w 10-minutową przerwę.

Czysta logika, bez FastAPI i bez muzyki, dzięki czemu da się ją testować
ze sztucznym zegarem. Serwer (app.py) tylko pyta o fazę i reaguje na nią.

Fazy:
  off       tryb wyłączony
  watching  czekamy, aż focus spadnie poniżej progu
  offer     focus był niski wystarczająco długo: gra utwór przerwy i czekamy na decyzję
  active    przerwa trwa, program jest zawieszony
"""

import time

OFF = "off"
WATCHING = "watching"
OFFER = "offer"
ACTIVE = "active"

# Zdarzenia zwracane z update()
EVENT_OFFER = "offer"  # właśnie zaproponowano przerwę
EVENT_BREAK_ENDED = "break_ended"  # przerwa skończyła się sama (minął czas)


class BreakMonitor:
    def __init__(
        self,
        threshold: float,
        low_seconds: float,
        break_seconds: float,
        cooldown_seconds: float,
        grace_seconds: float,
        clock=time.time,
    ):
        self.threshold = threshold
        self._low_seconds = low_seconds
        self._break_seconds = break_seconds
        self._cooldown_seconds = cooldown_seconds
        self._grace_seconds = grace_seconds
        self._clock = clock  # podmienialny zegar (testy)

        self.phase = OFF
        self.ends_at = None  # kiedy kończy się przerwa (czas unix), tylko w fazie active
        self._low_since = None  # od kiedy focus jest niski
        self._quiet_until = 0.0  # do tego czasu nie proponujemy przerwy

    @property
    def enabled(self) -> bool:
        return self.phase != OFF

    def set_enabled(self, enabled: bool) -> None:
        """Włącza lub wyłącza tryb. Wyłączenie kończy każdą fazę."""
        if enabled and self.phase == OFF:
            self.phase = WATCHING
        elif not enabled:
            self.phase = OFF
            self.ends_at = None
            self._low_since = None

    def update(self, focus: float | None) -> str | None:
        """Wołane co tik. Podaj aktualny focus (w fazie active może być None)."""
        now = self._clock()

        if self.phase == ACTIVE:
            if now >= self.ends_at:
                self._finish_break(now)
                return EVENT_BREAK_ENDED
            return None

        if self.phase != WATCHING or focus is None:
            return None

        if now < self._quiet_until or focus >= self.threshold:
            self._low_since = None  # focus wrócił do normy albo trwa cooldown
            return None

        if self._low_since is None:
            self._low_since = now
        if now - self._low_since >= self._low_seconds:
            self.phase = OFFER
            self._low_since = None
            return EVENT_OFFER
        return None

    def accept(self) -> bool:
        """Użytkownik zgodził się na przerwę. Zwraca True, jeśli faza się zmieniła."""
        if self.phase != OFFER:
            return False
        self.phase = ACTIVE
        self.ends_at = self._clock() + self._break_seconds
        return True

    def dismiss(self) -> bool:
        """Użytkownik odpowiedział "Nie teraz": wracamy do obserwacji z cooldownem."""
        if self.phase != OFFER:
            return False
        self.phase = WATCHING
        self._quiet_until = self._clock() + self._cooldown_seconds
        self._low_since = None
        return True

    def force_offer(self) -> str | None:
        """Przycisk testowy: od razu przechodzi do fazy budzenia (tylko z fazy watching)."""
        if self.phase == OFF:
            self.phase = WATCHING
        if self.phase != WATCHING:
            return None
        self.phase = OFFER
        self._low_since = None
        return EVENT_OFFER

    def end(self) -> bool:
        """Użytkownik kończy przerwę wcześniej."""
        if self.phase != ACTIVE:
            return False
        self._finish_break(self._clock())
        return True

    def _finish_break(self, now: float) -> None:
        self.phase = WATCHING
        self.ends_at = None
        self._low_since = None
        self._quiet_until = now + self._grace_seconds

    def snapshot(self) -> dict:
        """Stan do wysłania do UI."""
        return {
            "enabled": self.enabled,
            "phase": self.phase,
            "threshold": self.threshold,
            "ends_at": self.ends_at,
        }
