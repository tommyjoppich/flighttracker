"""Build docs/index.html: an interactive web dashboard for the Dallas trip.

Called at the end of analyze.py on every run. GitHub Pages serves docs/ as a
website (see README → "Turn on the website").
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

import config

ROOT = Path(__file__).parent
PRICES_CSV = ROOT / "data" / "prices.csv"
OPTIONS_CSV = ROOT / "data" / "options.csv"
TEMPLATE = ROOT / "dashboard_template.html"
OUT = ROOT / "docs" / "index.html"


def _num(x):
    return None if x is None or pd.isna(x) else int(round(float(x)))


def _hour(h: int) -> str:
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def _trip_text() -> str:
    def leg(s, day):
        return f"{day} {date.fromisoformat(s['date']):%b %-d} {s['from']}→{s['to']} after {_hour(s['earliest_hour'])}"
    return f"{leg(config.OUTBOUND, 'Thu')} · {leg(config.RETURN, 'Sun')}"


def build(signal: dict | None = None, by_hour=None, by_day=None, days_tracked: int = 0,
          min_days: int = 7):
    if not PRICES_CSV.exists() or not TEMPLATE.exists():
        return
    raw = pd.read_csv(PRICES_CSV)

    # ---- one row per check (each hourly run = up to 3 searches)
    checks = []
    for (utc, local), g in raw.groupby(["checked_at_utc", "checked_at_local"], sort=True):
        p = {r.search: (r.cheapest_price if r.status == "ok" else None) for r in g.itertuples()}
        out, ret, rt = (_num(p.get(k)) for k in ("outbound", "return", "roundtrip"))
        ow = out + ret if out is not None and ret is not None else None
        best = min([v for v in (rt, ow) if v is not None], default=None)
        errs = [str(r.error) for r in g.itertuples() if r.status != "ok" and pd.notna(r.error)]
        checks.append({"t": local, "rt": rt, "ow": ow, "out": out, "ret": ret, "best": best,
                       "err": errs[0][:120] if errs else None})

    # ---- latest flight list + per-flight price history
    latest_opts, flights = {}, []
    if OPTIONS_CSV.exists():
        opts = pd.read_csv(OPTIONS_CSV)
        if not opts.empty:
            last = opts["checked_at_utc"].max()
            for s, g in opts[opts["checked_at_utc"] == last].groupby("search"):
                latest_opts[s] = [{"p": int(r.price), "d": r.depart, "a": r.arrive, "s": int(r.stops),
                                   "m": int(r.duration_min)} for r in g.sort_values("price").itertuples()]
            local_of = dict(zip(raw["checked_at_utc"], raw["checked_at_local"]))
            opts["day"] = opts["checked_at_utc"].map(local_of).str[:10]
            for (s, d, a, st), g in opts[opts["search"].isin(["outbound", "return"])] \
                    .groupby(["search", "depart", "arrive", "stops"]):
                daily = g.groupby("day")["price"].min().sort_index()
                cur = g[g["checked_at_utc"] == last]["price"]
                flights.append({"leg": s, "d": d, "a": a, "s": int(st),
                                "now": _num(cur.min()) if not cur.empty else None,
                                "low": _num(g["price"].min()), "high": _num(g["price"].max()),
                                "seen": int(g["checked_at_utc"].nunique()),
                                "series": [int(v) for v in daily.tail(120)]})
            flights.sort(key=lambda f: (f["leg"] != "outbound", f["d"]))

    def bars(agg, label):
        if agg is None or len(agg) < 2:
            return []
        return [{"k": label(k), "v": round(float(r.vs_typical), 1), "avg": _num(r.avg_price),
                 "n": int(r.checks)} for k, r in agg.iterrows()]

    data = {
        "updated": raw["checked_at_local"].iloc[-1],
        "trip": _trip_text(),
        "fare": f"{config.ADULTS} adult · {config.SEAT}"
                + (" (no Basic Economy)" if config.EXCLUDE_BASIC_ECONOMY else ""),
        "target": config.TARGET_PRICE,
        "depart_date": config.OUTBOUND["date"],
        "days_left": int(raw["days_to_departure"].iloc[-1]),
        "signal": signal or {"level": "wait", "text": "Not enough data yet."},
        "checks": checks,
        "latest": latest_opts,
        "flights": flights,
        "by_hour": bars(by_hour, _hour),
        "by_day": bars(by_day, lambda d: d[:3]),
        "patterns_ready": days_tracked >= min_days,
        "days_tracked": days_tracked,
        "min_days": min_days,
    }
    OUT.parent.mkdir(exist_ok=True)
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(TEMPLATE.read_text().replace("/*__DATA__*/null", blob))
