"""Powiadomienia systemowe Windows (toast) dla trybu przerwy.

To dodatek: gdy biblioteki `windows-toasts` brak (inny system, brak instalacji) albo coś pójdzie nie tak,
używamy NullNotifier i działa sam baner w aplikacji.

BreakFlow woła trzy metody:
    show_offer(on_stop, on_not_now, track)   powiadomienie z przyciskami "Stop music" i "Not now"
    close_offer()                            zamyka je, gdy decyzja zapadła gdzie indziej (np. na stronie)
    show_break_over()                        krótka informacja po zakończeniu przerwy
Funkcje on_stop i on_not_now są wołane z wątku systemu Windows, w naszym procesie (bez przeglądarki).
"""

import sys
import threading

AUMID = "neurhon.ui"  # nazwa aplikacji w Windows; rejestruje ją notify_setup.py (jednorazowo)
STOP = "stop"
NOT_NOW = "not_now"


class NullNotifier:
    """Nic nie pokazuje. Używany, gdy powiadomienia systemowe są niedostępne."""

    def show_offer(self, on_stop, on_not_now, track):
        pass

    def close_offer(self):
        pass

    def show_break_over(self):
        pass


class DesktopNotifier:
    def __init__(self, aumid: str | None = None, toaster=None):
        from windows_toasts import InteractableWindowsToaster

        self._toaster = toaster or InteractableWindowsToaster("neurhon", aumid)
        self._offer = None  # trzymamy referencję, żeby powiadomienie nie zniknęło z pamięci
        self._lock = threading.Lock()

    def show_offer(self, on_stop, on_not_now, track):
        from windows_toasts import Toast, ToastButton, ToastScenario

        actions = {STOP: on_stop, NOT_NOW: on_not_now}

        def activated(event):
            with self._lock:
                self._offer = None
            action = actions.get(event.arguments)
            if action is not None:  # kliknięcie w sam tekst powiadomienia nic nie robi
                action()

        toast = Toast(
            ["Your focus dropped", f"Playing {track.title} until you decide. Stopping the music starts a 10 minute break."],
            scenario=ToastScenario.Reminder,  # zostaje na ekranie, dopóki użytkownik nie zareaguje
            on_activated=activated,
            on_dismissed=lambda event: None,
        )
        toast.AddAction(ToastButton("Stop music", STOP))
        toast.AddAction(ToastButton("Not now", NOT_NOW))
        with self._lock:
            self.close_offer_locked()
            self._offer = toast
        self._toaster.show_toast(toast)

    def close_offer_locked(self):
        toast, self._offer = self._offer, None
        if toast is not None:
            try:
                self._toaster.remove_toast(toast)
            except Exception as error:
                print(f"notify: could not remove toast: {error!r}")

    def close_offer(self):
        with self._lock:
            self.close_offer_locked()

    def show_break_over(self):
        from windows_toasts import Toast

        self._toaster.show_toast(Toast(["Break over", "Back to work when you are ready."]))


def create_notifier():
    """Zwraca DesktopNotifier, a gdy to niemożliwe, NullNotifier (sam baner)."""
    if sys.platform != "win32":
        return NullNotifier()
    try:
        from neurhon.server.notify_setup import is_registered

        return DesktopNotifier(AUMID if is_registered() else None)
    except Exception as error:
        print(f"notify: desktop notifications unavailable, using the in-app banner only ({error!r})")
        return NullNotifier()
