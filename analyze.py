"""Turn data/prices.csv into REPORT.md + charts, like a stock dashboard.

Answers:
  * What's the price right now, and is it the all-time low?
  * Which hour of the day (Chicago time) tends to be cheapest?
  * Which day of the week tends to be cheapest?
  * Is it cheaper to book a round trip or two one-ways?
  * Buy or wait?

Hour/weekday effects are measured *relative to the surrounding prices* (each
check is compared to that day's / that week's average), so a slow upward drift
over the months doesn't masquerade as a "cheap hour".
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates
import matplotlib.pyplot as plt
import pandas as pd

import config
import dashboard

ROOT = Path(__file__).parent
PRICES_CSV = ROOT / "data" / "prices.csv"
CHARTS = ROOT / "charts"
REPORT = ROOT / "REPORT.md"
ALERT = ROOT / "alert.md"          # written only when an alert should go out

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MIN_DAYS_FOR_PATTERNS = 7


def money(x) -> str:
    return "—" if pd.isna(x) else f"${x:,.0f}"


def hour_label(h: int) -> str:
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def style(ax, title, ylabel="Price (USD)"):
    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=12, fontweight="bold")
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


# ------------------------------------------------------------------ loading
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(PRICES_CSV)
    raw["t"] = pd.to_datetime(raw["checked_at_local"])
    ok = raw[raw["status"] == "ok"].copy()
    ok["cheapest_price"] = ok["cheapest_price"].astype(float)
    wide = ok.pivot_table(index="t", columns="search", values="cheapest_price", aggfunc="min")
    wide = wide.sort_index()
    if {"outbound", "return"} <= set(wide.columns):
        wide["two_one_ways"] = wide["outbound"] + wide["return"]
    # "best" = cheapest way to book the whole trip at that moment
    cols = [c for c in ("roundtrip", "two_one_ways") if c in wide.columns]
    wide["best"] = wide[cols].min(axis=1)
    wide["hour"] = wide.index.hour
    wide["weekday"] = wide.index.day_name()
    wide["day"] = wide.index.date
    wide["week"] = wide.index.to_period("W")
    return raw, wide


# ------------------------------------------------------------------ charts
def chart_history(wide, path):
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    if "roundtrip" in wide:
        ax.plot(wide.index, wide["roundtrip"], color=BLUE, lw=2, label="Round trip")
    if "two_one_ways" in wide:
        ax.plot(wide.index, wide["two_one_ways"], color=ORANGE, lw=2, label="Two one-ways")
    low_t = wide["best"].idxmin()
    ax.scatter([low_t], [wide["best"].min()], s=60, color=INK, zorder=5,
               edgecolor="white", linewidth=2)
    near_end = low_t >= wide.index[0] + (wide.index[-1] - wide.index[0]) * 0.75
    ax.annotate(f"All-time low {money(wide['best'].min())}", (low_t, wide["best"].min()),
                xytext=(-10 if near_end else 10, -4), textcoords="offset points",
                ha="right" if near_end else "left", va="top", color=INK, fontsize=9)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
    style(ax, "Total trip price over time")
    ax.legend(frameon=False, loc="upper left", labelcolor=MUTED)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_bars(agg, labels, title, path):
    fig, ax = plt.subplots(figsize=(10, 3.6), dpi=150)
    vals = agg["vs_typical"]
    colors = [BLUE if v == vals.min() else "#a9c6ec" for v in vals]
    ax.bar(range(len(vals)), vals, color=colors, width=0.8)
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_xticks(range(len(vals)), labels, fontsize=8)
    style(ax, title, "vs. typical price (USD)")
    i = int(vals.values.argmin())
    ax.annotate(f"−${abs(vals.iloc[i]):.0f}" if vals.iloc[i] < 0 else f"+${vals.iloc[i]:.0f}", (i, vals.iloc[i]), xytext=(0, -12),
                textcoords="offset points", ha="center", color=INK, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ------------------------------------------------------------------ report
def main():
    if not PRICES_CSV.exists():
        print("No data yet.")
        return
    raw, wide = load()
    CHARTS.mkdir(exist_ok=True)
    if ALERT.exists():
        ALERT.unlink()

    # consecutive failures (so you know if Google started blocking the bot)
    last_checks = raw.groupby("checked_at_utc")["status"].apply(lambda s: (s == "ok").any())
    fail_streak = 0
    for ok in reversed(last_checks.tolist()):
        if ok:
            break
        fail_streak += 1

    lines = [f"# ✈️ United ORD ⇄ DFW price tracker",
             "",
             f"**Trip:** Thu Feb 25 2027 ORD→DFW after 4 PM · Sun Feb 28 2027 DFW→ORD after 4 PM · "
             f"{config.ADULTS} adult, {config.SEAT}"
             f"{' (no Basic Economy)' if config.EXCLUDE_BASIC_ECONOMY else ''}",
             f"_Updated {raw['checked_at_local'].iloc[-1]} Chicago time · "
             f"{last_checks.size} checks so far · all times Chicago_",
             ""]

    if fail_streak:
        lines += [f"> ⚠️ The last {fail_streak} check(s) failed. Latest error: "
                  f"`{raw['error'].dropna().iloc[-1] if raw['error'].notna().any() else '?'}`", ""]

    if wide.empty or wide["best"].dropna().empty:
        lines.append("No successful price checks yet.")
        REPORT.write_text("\n".join(lines) + "\n")
        try:
            dashboard.build()
        except Exception as e:
            print(f"Dashboard not updated: {e}")
        return

    best = wide["best"].dropna()
    now_price, now_t = best.iloc[-1], best.index[-1]
    low, low_t = best.min(), best.idxmin()
    high = best.max()
    prev_low = best.iloc[:-1].min() if len(best) > 1 else None
    pct = (best < now_price).mean() * 100  # % of past checks that were cheaper
    days_tracked = (best.index[-1] - best.index[0]).days
    days_left = int(raw["days_to_departure"].iloc[-1])

    rt = wide["roundtrip"].dropna().iloc[-1] if "roundtrip" in wide and wide["roundtrip"].notna().any() else None
    ow = wide["two_one_ways"].dropna().iloc[-1] if "two_one_ways" in wide and wide["two_one_ways"].notna().any() else None
    how = "round trip" if ow is None or (rt is not None and rt <= ow) else "two one-way tickets"

    # ---- signal
    near_low = now_price <= low * 1.03
    hit_target = config.TARGET_PRICE is not None and now_price <= config.TARGET_PRICE
    if hit_target:
        sig = ("buy", "BUY", f"At or below your target of {money(config.TARGET_PRICE)}.")
    elif days_left <= 21:
        sig = ("soon", "BUY SOON", "Inside 3 weeks of departure, domestic fares usually only go up."
               + (" And this is at/near the all-time low." if near_low else ""))
    elif now_price == low and len(best) > 1:
        sig = ("buy", "BUY", "This is the lowest price the bot has ever seen.")
    elif near_low:
        sig = ("good", "GOOD PRICE", f"Within 3% of the all-time low ({money(low)}).")
    else:
        sig = ("wait", "WAIT", f"{pct:.0f}% of past checks were cheaper; the low is {money(low)}.")
    icon = {"buy": "🟢", "good": "🟢", "soon": "🟠", "wait": "⚪"}[sig[0]]
    signal = f"{icon} **{sig[1]}** — {sig[2]}"

    lines += [
        "## Right now",
        "",
        signal,
        "",
        "| | |",
        "|---|---|",
        f"| **Cheapest way to book now** | **{money(now_price)}** as a {how} |",
        f"| Round trip | {money(rt)} |",
        f"| Two one-ways (out + back) | {money(ow)} |",
        f"| All-time low | {money(low)} on {low_t:%a %b %d, %I %p} |",
        f"| All-time high | {money(high)} |",
        f"| Average | {money(best.mean())} |",
        f"| Days until departure | {days_left} |",
        "",
    ]

    latest = raw[raw["status"] == "ok"].groupby("search").tail(1).set_index("search")
    if not latest.empty:
        lines += ["**Cheapest flights right now**", "", "| Search | Price | Flight | Cheapest nonstop |",
                  "|---|---|---|---|"]
        for k, name in (("outbound", "Thu ORD→DFW"), ("return", "Sun DFW→ORD"), ("roundtrip", "Round trip (outbound shown)")):
            if k in latest.index:
                r = latest.loc[k]
                lines.append(f"| {name} | {money(float(r['cheapest_price']))} | {r['cheapest_flight']} | "
                             f"{money(pd.to_numeric(r['cheapest_nonstop_price'], errors='coerce'))} |")
        lines.append("")

    # ---- charts + patterns
    chart_history(wide, CHARTS / "history.png")
    lines += ["## Price history", "", "![Price history](charts/history.png)", ""]

    enough = days_tracked >= MIN_DAYS_FOR_PATTERNS
    caveat = "" if enough else (f"> ⏳ Only {days_tracked} day(s) of data — patterns below are "
                                f"unreliable until about {MIN_DAYS_FOR_PATTERNS} days.\n")

    s = wide[["best", "hour", "weekday", "day", "week"]].dropna(subset=["best"])
    by_hour = (s.assign(rel=s["best"] - s.groupby("day")["best"].transform("mean"))
                .groupby("hour").agg(avg_price=("best", "mean"), vs_typical=("rel", "mean"),
                                     checks=("best", "size")).sort_index())
    by_day = (s.assign(rel=s["best"] - s.groupby("week")["best"].transform("mean"))
               .groupby("weekday").agg(avg_price=("best", "mean"), vs_typical=("rel", "mean"),
                                       checks=("best", "size")))
    by_day = by_day.reindex([d for d in WEEKDAYS if d in by_day.index])

    def spread_note(agg, what):
        spread = agg["vs_typical"].max() - agg["vs_typical"].min()
        if spread < 5:
            return f"Differences by {what} are under $5 — effectively no pattern so far, so don't wait around for a specific {what}."
        return ""

    if len(by_hour) > 1:
        chart_bars(by_hour, [hour_label(h) for h in by_hour.index],
                   "Cheapest time of day to buy (Chicago)", CHARTS / "by_hour.png")
        bh = by_hour["vs_typical"].idxmin()
        lines += ["## Best time of day", "", caveat,
                  f"Cheapest hour so far: **{hour_label(bh)}**, about "
                  f"**${abs(by_hour.loc[bh, 'vs_typical']):.0f} below** that day's average.",
                  spread_note(by_hour, "hour"), "", "![By hour](charts/by_hour.png)", ""]

    if len(by_day) > 1:
        chart_bars(by_day, [d[:3] for d in by_day.index],
                   "Cheapest day of the week to buy", CHARTS / "by_weekday.png")
        bd = by_day["vs_typical"].idxmin()
        lines += ["## Best day of the week", "", caveat,
                  f"Cheapest day so far: **{bd}**, about "
                  f"**${abs(by_day.loc[bd, 'vs_typical']):.0f} below** that week's average.",
                  spread_note(by_day, "day"), "", "![By weekday](charts/by_weekday.png)", "",
                  "| Day | Avg price | vs. typical | Checks |", "|---|---|---|---|"]
        for d, r in by_day.iterrows():
            lines.append(f"| {d} | {money(r['avg_price'])} | {r['vs_typical']:+.0f} | {int(r['checks'])} |")
        lines.append("")

    # daily lows table (last 14 days)
    daily = best.groupby(best.index.date).agg(["min", "max", "mean"]).tail(14)
    lines += ["## Daily range (last 14 days)", "", "| Date | Low | High | Avg |", "|---|---|---|---|"]
    for d, r in daily[::-1].iterrows():
        lines.append(f"| {d:%a %b %d} | {money(r['min'])} | {money(r['max'])} | {money(r['mean'])} |")
    lines.append("")
    lines.append("_Raw data: `data/prices.csv` (one row per search per hour) and `data/options.csv` (every United flight seen)._")

    REPORT.write_text("\n".join(l for l in lines if l is not None) + "\n")
    try:
        dashboard.build({"level": sig[0], "label": sig[1], "text": sig[2]},
                        by_hour, by_day, days_tracked, MIN_DAYS_FOR_PATTERNS)
    except Exception as e:  # never let the website break the price tracking
        print(f"Dashboard not updated: {e}")

    # ---- alert
    reasons = []
    # skip the first 2 days (every price is a "new low" at first) and $1-2 wiggles
    if prev_low is not None and now_price <= prev_low - 3 and len(best) > 48:
        reasons.append(f"New all-time low: **{money(now_price)}** (previous low {money(prev_low)}).")
    if hit_target and (len(best) < 2 or best.iloc[-2] > config.TARGET_PRICE):
        reasons.append(f"Price dropped to your target: **{money(now_price)}** ≤ {money(config.TARGET_PRICE)}.")
    if reasons:
        ALERT.write_text(
            f"{' '.join(reasons)}\n\nCheapest way to book: {how}. Checked {now_t:%a %b %d %I:%M %p} Chicago time.\n\n"
            "Book on united.com — prices can change within the hour.\n"
        )
        print("ALERT:", " ".join(reasons))

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write(f"alert={'true' if reasons else 'false'}\n")
            fh.write(f"price={now_price:.0f}\n")
    print(f"Now {money(now_price)} | low {money(low)} | {signal}")


if __name__ == "__main__":
    main()
