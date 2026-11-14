"""Settings that the server and the UI share: moods, metrics, paths, secrets.

Teammates add a new mood label or metric here, and the UI picks it up.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from neurhon.server.interfaces import Track


@dataclass(frozen=True)
class Metric:
    """Metryka taka jak arousal valence itd."""

    id: str
    title: str
    description: str


@dataclass(frozen=True)
class MoodLabel:
    """Określony stan emocjonalny i jego zmienne"""

    id: str
    title: str
    color: str
    energy: float  # pozycja na mapie: góra/dół (niska/wysoka energia)
    valence: float  # pozycja na mapie: lewo/prawo (nieprzyjemne/przyjemne)


METRICS = [
    Metric("valence", "Valence", "How pleasant the state is, from unpleasant to pleasant."),
    Metric("energy", "Energy", "How energized you are, from sleepy to alert."),
    Metric("focus", "Focus", "How concentrated you are, from distracted to locked in."),
] # trzy sygnały rejestrowane przez opaskę

MOOD_LABELS = [
    MoodLabel("calm", "Calm", "#4f8cff", energy=0.2, valence=0.7),
    MoodLabel("focused", "Focused", "#2fbf9b", energy=0.6, valence=0.6),
    MoodLabel("stressed", "Stressed", "#ef5b5b", energy=0.85, valence=0.2),
    MoodLabel("tired", "Tired", "#a58bd9", energy=0.15, valence=0.3),
] # przykładowe stany emocjonalne które będziemy wykorzystywać.

DATA_DIR = Path("data")
HISTORY_PATH = DATA_DIR / "history.jsonl" #main ścieżka zakodowana

# ---- tryb przerwy ----
FOCUS_THRESHOLD_DEFAULT = 0.30  # poniżej tego focusu proponujemy przerwę
LOW_FOCUS_SECONDS = 20  # tyle sekund focus musi być niski z rzędu
BREAK_MINUTES = 10  # długość przerwy (program zawieszony)
BREAK_COOLDOWN_MINUTES = 10  # po "Not now" focus nie jest mierzony przez tyle minut
BREAK_GRACE_MINUTES = 0  # po przerwie focus jest mierzony od razu (wcześniejsze zakończenie jest na własne ryzyko)

# Muzyka pobudzająca: gra w pętli (jeden losowy utwór), dopóki użytkownik nie kliknie "Stop music" lub "Not now".
WAKE_VOLUME = 80  # głośność (0..100) na czas muzyki pobudzającej, potem wraca poprzednia
WAKE_TRACKS = [
    Track("Never Gonna Give You Up", "Rick Astley", "Wake up"),
    Track("Thunderstruck", "AC/DC", "Wake up"),
    Track("Enter Sandman", "Metallica", "Wake up"),
    Track("Master of Puppets", "Metallica", "Wake up"),
]


@lru_cache(maxsize=1)
def load_env(path: str = ".env") -> dict[str, str]:
    """Czytanie sekretów  .env"""
    env_file = Path(path)
    if not env_file.exists():
        return {} # jak nie ma to nie gg tylko słownik zwraca

    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1) # potem moze byc myslnik bez problemu
        values[key.strip()] = value.strip().strip('"').strip("'") # zdejmuje cudzysłowy z wartości
    return values


def get_setting(name: str, default: str | None = None) -> str | None:
    """Gdzie dokładnie leży sekret"""
    return os.environ.get(name) or load_env().get(name) or default
