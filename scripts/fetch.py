#!/usr/bin/env python3
"""Holt die Fahrten aller Teilnehmer aus intervals.icu, rechnet die Wertung und schreibt site/data.json.

Umgebung:
  INTERVALS_API_KEY        Key mit Lesezugriff auf alle Teilnehmer (Coach-Zugriff)
  <key_env aus config>     optional: eigener Key pro Teilnehmer, falls Coach-Zugriff nicht klappt
Nur Datum, Startzeit, Dauer, Distanz (km), Trainingsbelastung (TSS) und Indoor/Outdoor landen in data.json – keine Watt, kein Puls, keine GPS-Strecken.
"""
import base64, json, os, sys, urllib.error, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
BASE = "https://intervals.icu/api/v1"
TZ = ZoneInfo(CFG.get("timezone", "Europe/Berlin"))
START = date.fromisoformat(CFG["start"])
END = date.fromisoformat(CFG["end"])
TYPES = set(CFG["ride_types"])
MIN_SEC = CFG.get("min_ride_minutes", 20) * 60
BONUS_N = CFG.get("bonus_week_min_rides", 3)


def get(path, key, params):
    url = f"{BASE}{path}?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        "Authorization": "Basic " + base64.b64encode(f"API_KEY:{key}".encode()).decode(),
        "Accept": "application/json",
        "User-Agent": "rollenkampf-dashboard/1.0",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def week_start(d):
    return d - timedelta(days=d.weekday())


def fetch_rides(p, today):
    key = os.environ.get(p.get("key_env") or "", "") or os.environ.get("INTERVALS_API_KEY", "")
    if not p.get("athlete_id"):
        return [], "noch nicht verbunden", 0
    if not key:
        return [], "kein API-Key", 0
    try:
        acts = get(f"/athlete/{p['athlete_id']}/activities", key,
                   {"oldest": START.isoformat(), "newest": min(today, END).isoformat()})
    except urllib.error.HTTPError as e:
        return [], f"kein Zugriff (HTTP {e.code})", 0
    except Exception as e:  # noqa: BLE001
        return [], f"Fehler: {type(e).__name__}", 0
    rides, strava_only = [], 0
    for a in acts:
        if a.get("source") == "STRAVA" and not a.get("moving_time"):
            strava_only += 1
            continue
        if a.get("type") not in TYPES:
            continue
        sec = int(a.get("moving_time") or 0)
        if sec <= 0:
            continue
        ts = a["start_date_local"]
        rides.append({"date": ts[:10], "time": ts[11:16], "sec": sec,
                      "km": round((a.get("distance") or 0) / 1000, 1),
                      "tss": int(round(a.get("icu_training_load") or 0)),
                      "indoor": bool(a.get("trainer")) or a.get("type") == "VirtualRide",
                      "manual": False})
    return rides, None, strava_only


def manual_rides(name):
    out = []
    for m in json.loads((ROOT / "manual.json").read_text(encoding="utf-8") or "[]"):
        if m.get("name") == name:
            out.append({"date": m["date"], "time": m.get("time", ""), "sec": int(m["minutes"]) * 60,
                        "km": float(m.get("km", 0)),
                        "tss": int(m.get("tss", 0)),
                        "indoor": m.get("indoor", True), "manual": True})
    return out


def stats(rides, weeks):
    by_week = {w: {"sec": 0, "km": 0.0, "tss": 0, "n": 0} for w in weeks}
    for r in rides:
        w = week_start(date.fromisoformat(r["date"])).isoformat()
        if w in by_week:
            by_week[w]["sec"] += r["sec"]
            by_week[w]["km"] = round(by_week[w]["km"] + r["km"], 1)
            by_week[w]["tss"] += r["tss"]
            if r["sec"] >= MIN_SEC:
                by_week[w]["n"] += 1
    bonus = [w for w in weeks if by_week[w]["n"] >= BONUS_N]
    # Serie: aufeinanderfolgende Bonuswochen bis zur letzten abgeschlossenen bzw. laufenden Woche
    streak = 0
    for i, w in enumerate(reversed(weeks)):
        if by_week[w]["n"] >= BONUS_N:
            streak += 1
        elif i == 0:  # laufende Woche zählt nicht gegen die Serie
            continue
        else:
            break
    best = max(rides, key=lambda r: r["sec"], default=None)
    best_km = max(rides, key=lambda r: r["km"], default=None)
    return {
        "total_sec": sum(r["sec"] for r in rides),
        "total_km": round(sum(r["km"] for r in rides), 1),
        "total_tss": sum(r["tss"] for r in rides),
        "longest_km": best_km["km"] if best_km else 0,
        "longest_km_date": best_km["date"] if best_km else None,
        "rides": len(rides),
        "indoor_sec": sum(r["sec"] for r in rides if r["indoor"]),
        "bonus_weeks": len(bonus),
        "streak": streak,
        "longest_sec": best["sec"] if best else 0,
        "longest_date": best["date"] if best else None,
        "early": sum(1 for r in rides if r["time"] and r["time"] < "07:00"),
        "late": sum(1 for r in rides if r["time"] and r["time"] >= "21:00"),
        "max_week_rides": max((v["n"] for v in by_week.values()), default=0),
        "weeks": {w: by_week[w] for w in weeks},
    }


def main():
    now = datetime.now(TZ)
    today = now.date()
    last = min(today, END)
    weeks = []
    w = week_start(START)
    while w <= last:
        weeks.append(w.isoformat())
        w += timedelta(days=7)
    out = []
    for p in CFG["participants"]:
        rides, err, strava_only = fetch_rides(p, today)
        rides += manual_rides(p["name"])
        rides = sorted((r for r in rides if START.isoformat() <= r["date"] <= last.isoformat()),
                       key=lambda r: (r["date"], r["time"]))
        out.append({"name": p["name"], "error": err, "strava_only": strava_only,
                    "rides_list": rides, **stats(rides, weeks)})
        print(f"{p['name']}: {len(rides)} Fahrten, {sum(r['sec'] for r in rides) / 3600:.1f} h, {sum(r['km'] for r in rides):.0f} km, {sum(r['tss'] for r in rides)} TSS"
              + (f"  [{err}]" if err else ""))
    data = {"title": CFG["title"], "season": CFG["season"], "start": CFG["start"], "end": CFG["end"],
            "bonus_week_min_rides": BONUS_N, "min_ride_minutes": MIN_SEC // 60,
            "updated": now.isoformat(timespec="minutes"), "weeks": weeks, "participants": out}
    (ROOT / "site" / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if all(p["error"] for p in out if CFG["participants"][out.index(p)].get("athlete_id")):
        sys.exit("Kein Teilnehmer konnte geladen werden.")


if __name__ == "__main__":
    main()
