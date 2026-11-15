# HOTB2k27 - neuρn

Muzyka dobierana na podstawie EEG (BrainAccess) -> SongScheduler -> Spotify, z panelem w przeglądarce.

## Uruchomienie
0. `pip install setuptools`
1. `pip install -e .`
2. Skopiuj `.env.example` do `.env` i uzupełnij klucze Spotify / Last.fm.
3. `neurhon-run` - pełny pipeline (opaska + Spotify + UI na http://127.0.0.1:8000).
4. `neurhon-ui` - samo UI na danych demo (bez opaski i Spotify).
