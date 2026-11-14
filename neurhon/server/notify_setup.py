"""Jednorazowa rejestracja nazwy aplikacji "neurhon" w Windows (tylko dla Twojego konta).

Po co: dzięki temu powiadomienia mają nazwę "neurhon" i ikonę ρ, a ich przyciski działają
także po przeniesieniu powiadomienia do Centrum akcji.

Co zapisuje: jeden klucz w rejestrze bieżącego użytkownika (bez uprawnień administratora):
    HKEY_CURRENT_USER\\Software\\Classes\\AppUserModelId\\neurhon.ui
        DisplayName          = "neurhon"
        IconUri              = <pełna ścieżka do neurhon/ui/img/favicon.png>
        IconBackgroundColor  = "FF141414"

Uruchomienie:   python -m neurhon.server.notify_setup
Usunięcie:      python -m neurhon.server.notify_setup --remove
"""

import argparse
import sys
from pathlib import Path

from neurhon.server.notify import AUMID

KEY_PATH = rf"Software\Classes\AppUserModelId\{AUMID}"
ICON = Path(__file__).resolve().parent.parent / "ui" / "img" / "favicon.png"


def is_registered() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH):
            return True
    except OSError:
        return False


def register() -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY_PATH) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "neurhon")
        winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(ICON))
        winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "FF141414")


def remove() -> None:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY_PATH)
    except OSError:
        pass  # nie było czego usuwać


def main() -> None:
    parser = argparse.ArgumentParser(description="Register or remove the neurhon notification identity (Windows)")
    parser.add_argument("--remove", action="store_true", help="remove the registry key again")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This is only needed on Windows.")
        return
    if args.remove:
        remove()
        print(f"Removed HKCU\\{KEY_PATH}")
    else:
        register()
        print(f"Registered HKCU\\{KEY_PATH} (icon: {ICON})")


if __name__ == "__main__":
    main()
