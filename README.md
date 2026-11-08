# 🚴 Rollenkampf

Winter-Challenge auf der Rolle: Wer fährt von November bis März die meiste Zeit?

Ein GitHub-Actions-Job holt stündlich die Fahrten aller Teilnehmer aus [intervals.icu](https://intervals.icu),
rechnet die Wertung und veröffentlicht das Dashboard auf GitHub Pages.

## Mitmachen
1. Konto auf intervals.icu anlegen.
2. Eigene Datenquelle verbinden (Garmin, Zwift, Wahoo, MyWhoosh …) – **nur Strava reicht nicht**,
   Strava-Aktivitäten gibt intervals.icu nicht über die API heraus.
3. Elias in intervals.icu als Coach hinzufügen.
4. Athleten-ID (`i…`, steht in der URL bzw. unter Settings) an Elias schicken → kommt in `config.json`.

## Dateien
| Datei | Zweck |
|---|---|
| `config.json` | Teilnehmer, Zeitraum, Regeln |
| `manual.json` | Fahrten von Hand nachtragen, z. B. `{"name": "Elias", "date": "2026-11-20", "minutes": 60}` |
| `scripts/fetch.py` | Holt Daten, rechnet Wertung, schreibt `site/data.json` |
| `site/index.html` | Dashboard (statisch, ohne Abhängigkeiten) |
| `.github/workflows/update.yml` | Stündlicher Lauf + Deployment auf Pages |

## Secrets
- `INTERVALS_API_KEY` – API-Key von Elias (liest per Coach-Zugriff alle Teilnehmer)
- optional `INTERVALS_KEY_FREUND1/2` – falls Coach-Zugriff nicht klappt

## Lokal testen
```bash
INTERVALS_API_KEY=... python3 scripts/fetch.py
cd site && python3 -m http.server   # → http://localhost:8000
```

## Datenschutz
In `data.json` landen nur Datum, Startzeit, Dauer und Rolle/draußen – keine Watt, kein Puls, keine Strecken.
