"""Contracts shared between the EEG side, the music side and the UI.

Everything in the system talks in terms of these types, so teammates can
work in parallel as long as they respect them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass  #omijamy pisanie initów itd. robi to za nas
class Mood:

    label: str  # nazwa stanu emocjonalnego
    scores: dict[str, float] = field(default_factory=dict) #metryki stan, odczyt stanu
    timestamp: float = 0.0 # czas odczytu stanu


class MoodProvider(ABC): #abstrakcyjna
    """ Interfejs który ma dostarczać aktualny stan emocjonalny"""

    @abstractmethod
    def get_mood(self) -> Mood:
        """Zwraca odczyt stanu"""


@dataclass
class Track:
    """Obecny utwór ma tytuł wykonawe i playlistę"""

    title: str
    artist: str
    playlist: str = ""


@dataclass
class PlaybackState:
    """Zapamiętany stan odtwarzacza. Wracamy do niego po muzyce pobudzającej."""

    track: Track | None
    playing: bool
    volume: int | None = None  # głośność 0..100, None gdy nieznana
    data: dict = field(default_factory=dict)  # dane implementacji (np. identyfikatory kontekstu i pozycja w Spotify)


class MusicController(ABC):
    """ Interfejs do sterowania odtwarzaczem muzyki. Ma wszystkie metody które są potrzebne do sterowania"""

    @abstractmethod
    def play(self) -> None:
        """Odtwarzaj muze."""

    @abstractmethod
    def pause(self) -> None:
        """Zapauzuj muze"""

    @abstractmethod
    def next_track(self) -> None:
        """Nastepny utwór"""

    @abstractmethod
    def play_track(self, track: Track, volume: int | None = None, repeat: bool = False) -> None:
        """Zagraj dokładnie ten utwór. volume (0..100) ustawia głośność, repeat=True powtarza utwór w pętli."""

    @abstractmethod
    def capture_state(self) -> PlaybackState:
        """Zapamiętaj, co teraz gra i jaka jest głośność (wołane tuż przed muzyką pobudzającą)."""

    @abstractmethod
    def restore_state(self, state: PlaybackState, resume: bool) -> None:
        """Przywróć głośność i wyłącz pętlę. Jeśli resume=True i wcześniej coś grało, wznów to,
        w przeciwnym razie tylko zatrzymaj muzykę."""

    @abstractmethod
    def now_playing(self) -> Track | None:
        """Co teraz jest grane"""

    @abstractmethod
    def is_playing(self) -> bool:
        """Czy wgl jest coś grane"""


@dataclass
class HistoryEntry:
    """To jest rekord w historii odtwarzania. Reason wskazuje dlaczego doszło do zmiany"""

    timestamp: float
    track: Track
    mood: Mood
    reason: str = "auto"


class HistoryStore(ABC):
    """Definiuje format zapisu do bazy danych (bądź do json file)"""

    @abstractmethod
    def append(self, entry: HistoryEntry) -> None:
        """Save one entry at the end of the history."""

    @abstractmethod
    def get_entries(self, limit: int = 100, since: float | None = None) -> list[HistoryEntry]:
        """Get the last `limit` entries, optionally only those after `since` timestamp."""

