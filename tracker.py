"""Check current United prices for the trip and append them to data/*.csv.

Run once per hour (GitHub Actions does this for you). Three searches per run:
  * outbound one-way   ORD→DFW  Thu Feb 25 after 4pm
  * return one-way     DFW→ORD  Sun Feb 28 after 4pm
  * round trip         both legs together (usually what you'd actually book)
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config

DATA = Path(__file__).parent / "data"
PRICES_CSV = DATA / "prices.csv"
OPTIONS_CSV = DATA / "options.csv"

PRICE_FIELDS = [
    "checked_at_utc", "checked_at_local", "local_hour", "local_weekday",
    "days_to_departure", "search", "status", "cheapest_price",
    "cheapest_nonstop_price", "num_options", "cheapest_flight", "error",
]
OPTION_FIELDS = [
    "checked_at_utc", "search", "price", "depart", "arrive", "stops",
    "duration_min", "airlines",
]


# ---------------------------------------------------------------- searching
def _leg(spec):
    from fast_flights import FlightQuery
    return FlightQuery(
        date=spec["date"],
        from_airport=spec["from"],
        to_airport=spec["to"],
        airlines=[config.AIRLINE_CODE],
        earliest_departure_hour=spec["earliest_hour"],
    )


def build_query(kind: str):
    from fast_flights import Passengers, create_query
    legs = {
        "outbound": [_leg(config.OUTBOUND)],
        "return": [_leg(config.RETURN)],
        "roundtrip": [_leg(config.OUTBOUND), _leg(config.RETURN)],
    }[kind]
    return create_query(
        flights=legs,
        seat=config.SEAT,
        trip="round-trip" if kind == "roundtrip" else "one-way",
        passengers=Passengers(adults=config.ADULTS),
        currency=config.CURRENCY,
        language="en-US",
        exclude_basic_economy=config.EXCLUDE_BASIC_ECONOMY,
    )


def fetch(kind: str, attempts: int = 3):
    from fast_flights import get_flights
    q = build_query(kind)
    last = None
    for i in range(attempts):
        try:
            return get_flights(q)
        except Exception as e:  # network hiccups, Google throttling, parse errors
            last = e
            time.sleep(10 * (i + 1))
    raise last


# ---------------------------------------------------------------- filtering
def _hhmm(dt) -> str:
    return f"{dt.time[0]:02d}:{dt.time[1]:02d}"


def united_options(results, kind: str) -> list[dict]:
    """Keep only all-United itineraries leaving at/after the earliest hour."""
    spec = config.RETURN if kind == "return" else config.OUTBOUND
    out = []
    for f in results:
        if not f.flights or not f.price:
            continue
        names = f.airlines or []
        if not names or not all(config.AIRLINE_NAME.lower() in n.lower() for n in names):
            continue
        first, last = f.flights[0], f.flights[-1]
        if first.departure.time[0] < spec["earliest_hour"]:
            continue
        out.append({
            "price": int(f.price),
            "depart": _hhmm(first.departure),
            "arrive": _hhmm(last.arrival),
            "stops": len(f.flights) - 1,
            "duration_min": sum(s.duration for s in f.flights),
            "airlines": "/".join(names),
        })
    out.sort(key=lambda o: o["price"])
    return out


def describe(o: dict) -> str:
    stops = "nonstop" if o["stops"] == 0 else f"{o['stops']} stop"
    return f"{o['depart']}→{o['arrive']} {stops}"


# ---------------------------------------------------------------- recording
def _append(path: Path, fields: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def run(fetcher=fetch, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(config.TIMEZONE))
    if local.date() > date.fromisoformat(config.STOP_AFTER):
        print("Trip has started — nothing left to track.")
        return []

    base = {
        "checked_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checked_at_local": local.strftime("%Y-%m-%d %H:%M"),
        "local_hour": local.hour,
        "local_weekday": local.strftime("%A"),
        "days_to_departure": (date.fromisoformat(config.OUTBOUND["date"]) - local.date()).days,
    }
    price_rows, option_rows = [], []
    for kind in ("outbound", "return", "roundtrip"):
        row = {**base, "search": kind}
        try:
            opts = united_options(fetcher(kind), kind)
            if not opts:
                raise RuntimeError("no matching United flights in results")
            nonstop = [o for o in opts if o["stops"] == 0]
            row.update(
                status="ok",
                cheapest_price=opts[0]["price"],
                cheapest_nonstop_price=nonstop[0]["price"] if nonstop else "",
                num_options=len(opts),
                cheapest_flight=describe(opts[0]),
                error="",
            )
            option_rows += [{"checked_at_utc": base["checked_at_utc"], "search": kind, **o} for o in opts]
            print(f"{kind:9s} ${opts[0]['price']:>5}  {describe(opts[0])}  ({len(opts)} options)")
        except Exception as e:
            row.update(status="error", cheapest_price="", cheapest_nonstop_price="",
                       num_options=0, cheapest_flight="", error=str(e)[:200])
            print(f"{kind:9s} ERROR: {e}", file=sys.stderr)
        price_rows.append(row)

    _append(PRICES_CSV, PRICE_FIELDS, price_rows)
    _append(OPTIONS_CSV, OPTION_FIELDS, option_rows)
    return price_rows


if __name__ == "__main__":
    run()
