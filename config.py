"""Trip settings. Edit these if your plans change."""

AIRLINE_CODE = "UA"          # Google Flights airline filter
AIRLINE_NAME = "United"      # name we require on every segment of a result

OUTBOUND = {
    "label": "Outbound ORD→DFW",
    "date": "2027-02-25",    # Thursday
    "from": "ORD",
    "to": "DFW",
    "earliest_hour": 16,     # departs 4:00 PM or later (local airport time)
}

RETURN = {
    "label": "Return DFW→ORD",
    "date": "2027-02-28",    # Sunday
    "from": "DFW",
    "to": "ORD",
    "earliest_hour": 16,
}

ADULTS = 1
SEAT = "economy"             # economy / premium-economy / business / first
CURRENCY = "USD"

# United's cheapest fares are usually Basic Economy (no seat choice, no full-size
# carry-on). Set True to track only Standard Economy and up.
EXCLUDE_BASIC_ECONOMY = True

# All analysis is done in Chicago time.
TIMEZONE = "America/Chicago"

# Stop checking once the outbound flight has departed.
STOP_AFTER = "2027-02-25"

# Alert (GitHub issue -> email) when the round-trip price hits a new all-time low,
# or drops below this target. Set to None to disable the target.
TARGET_PRICE = 300
