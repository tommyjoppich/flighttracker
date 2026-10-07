# ✈️ United ORD ⇄ DFW Flight Price Tracker

A free bot that checks United prices **every hour**, records them, and tells you
when to buy — like a stock chart for your plane ticket.

**Your trip:** Thu Feb 25 2027, ORD → DFW after 4 PM · Sun Feb 28 2027, DFW → ORD after 4 PM · United only.

Each hour it checks three prices on Google Flights:

| Search | Why |
|---|---|
| Outbound one-way (Thu, ORD→DFW, after 4 PM) | track each leg on its own |
| Return one-way (Sun, DFW→ORD, after 4 PM) | |
| Round trip (both legs together) | sometimes cheaper than two one-ways, sometimes not |

Then it updates **[REPORT.md](REPORT.md)** with:

- the current price and a **BUY / GOOD PRICE / WAIT** signal
- the **all-time low** (and when it happened)
- the **cheapest hour of the day** and **cheapest day of the week** to buy
- whether a round trip or two one-ways is cheaper right now
- charts of the price over time

And when the price hits a **new all-time low**, it opens a GitHub issue — which
GitHub emails to you automatically.

**Cost: $0.** It runs on GitHub Actions' free tier. No API keys, no credit card.

---

## Setup (about 10 minutes, no coding)

### 1. Make a GitHub account
Go to [github.com/signup](https://github.com/signup) if you don't have one.

### 2. Create a new repository
1. Click **+** (top right) → **New repository**.
2. Name it something like `flight-tracker`.
3. Choose **Public** (unlimited free minutes) or **Private** (also fine — this
   bot uses ~750 of your 2,000 free monthly minutes).
4. Click **Create repository**.

### 3. Upload these files
1. On the new repo's page, click **uploading an existing file**.
2. Unzip `flight-tracker.zip` on your computer and drag **everything inside the
   folder** into the upload box — including the hidden `.github` folder.
   - **Mac:** in Finder press `Cmd + Shift + .` to show hidden folders.
   - **Windows:** in File Explorer, View → Show → Hidden items.
   - If the `.github` folder won't upload, create it by hand: **Add file → Create
     new file**, type the name `.github/workflows/track.yml`, and paste in the
     contents of that file.
3. Click **Commit changes**.

### 4. Let the bot save data
1. Go to **Settings → Actions → General**.
2. Under **Workflow permissions**, pick **Read and write permissions**.
3. Click **Save**.

### 5. Run it once to test
1. Click the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Track flight prices** on the left → **Run workflow** → **Run workflow**.
3. After ~1 minute it turns green ✅. Go back to the **Code** tab and open
   **REPORT.md** — you'll see your first prices.

That's it. From now on it runs every hour on its own until Feb 25.

### 6. Get the email alerts
You're automatically "watching" your own repo, so new-low issues get emailed to you.
To double-check: the **Watch** button at the top of the repo should say
**All Activity**, and in [notification settings](https://github.com/settings/notifications)
"Email" should be checked under Watching.

---

## Changing settings

Everything lives in **`config.py`** (click it on GitHub → pencil icon to edit):

- `TARGET_PRICE = 250` — also alert you when it drops to $250 or less.
- `EXCLUDE_BASIC_ECONOMY = True` — United's cheapest fares are usually Basic
  Economy (no seat selection, no full-size carry-on). Turn this on if you'd never
  buy Basic. *(Tip: change this early — switching mid-way mixes two kinds of prices.)*
- `ADULTS`, dates, airports, `earliest_hour` — if your plans change.

## Reading the results honestly

- **Give it a week** before trusting the hour/day patterns. The report says so
  until it has enough data.
- Hour and weekday results are measured **against that day's/week's average**,
  so a slow upward creep over months doesn't fool it.
- Airfare "cheapest day to buy" folklore is mostly myth — if the report shows a
  spread of only a few dollars, there's no real pattern, and the **all-time low
  alert** is the thing to watch.
- Domestic fares usually rise sharply in the **last 2–3 weeks**; the report
  switches to **BUY SOON** inside 21 days.
- United lets you cancel for free within 24 hours of booking (when booked a week
  or more before departure), so if a lower price shows up the next day, you can
  cancel and rebook. The bot keeps running after you book, so you'll see it.

## Troubleshooting

| Problem | Fix |
|---|---|
| Red ❌ on "Save results" | Step 4 — set Read and write permissions. |
| Report says recent checks failed | Google sometimes blocks a request; occasional failures are normal and skipped. If *every* check fails for a day, the scraping library may need an update: change the version in `requirements.txt` to the newest from [pypi.org/project/fast-flights](https://pypi.org/project/fast-flights/). |
| Runs aren't exactly on the hour | Normal — GitHub's scheduler can run a few (sometimes 10–20) minutes late. |
| Want to stop it | Actions tab → Track flight prices → **⋯** → Disable workflow. |

## Files

| File | What it does |
|---|---|
| `tracker.py` | Fetches prices and appends them to `data/prices.csv` and `data/options.csv` |
| `analyze.py` | Builds `REPORT.md`, the charts, and the low-price alert |
| `config.py` | Your trip settings |
| `.github/workflows/track.yml` | Tells GitHub to run the bot every hour |

Prices come from Google Flights via the open-source
[fast-flights](https://github.com/AWeirdDev/flights) library. Always confirm the
final price on united.com before booking.
