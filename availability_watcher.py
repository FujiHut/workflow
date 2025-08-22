import os
import uuid
import psycopg2
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

# === Inline hut config (activity_id + ticket_ids) ===
# Fill in the REPLACE_ME entries using the JSON responses you collected.
# If a hut has multiple room/price options (tickets), list ALL of their ticket_ids here.
HUTS = {
    # KAMAIWAKAN — 6 separate room types (replace with your real IDs)
    "kamaiwakan": {
        "activity_id": "REPLACE_ME_KAMAIWAKAN_ACTIVITY",
        "ticket_ids": [
            # Paste all 6 ticket_ids you extracted for Kamaiwakan
            "REPLACE_ME_TICKET_ID_1",
            "REPLACE_ME_TICKET_ID_2",
            "REPLACE_ME_TICKET_ID_3",
            "REPLACE_ME_TICKET_ID_4",
            "REPLACE_ME_TICKET_ID_5",
            "REPLACE_ME_TICKET_ID_6",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/vP9OM",
    },

    "taiyokan": {
        "activity_id": "REPLACE_ME_TAIYOKAN_ACTIVITY",
        "ticket_ids": [
            # Add all ticket_ids you saw in the JSON
            "REPLACE_ME_TICKET_ID_1",
            "REPLACE_ME_TICKET_ID_2",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB",
    },

    "miharashikan": {
        "activity_id": "REPLACE_ME_MIHARASHIKAN_ACTIVITY",
        "ticket_ids": [
            "REPLACE_ME_TICKET_ID_1",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone",
    },

    "yamaguchiya": {
        "activity_id": "REPLACE_ME_YAMAGUCHIYA_ACTIVITY",
        "ticket_ids": [
            "REPLACE_ME_TICKET_ID_1",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me",
    },

    # SETOKAN — ✅ real IDs provided by you (6 options)
    "setokan": {
        "activity_id": "ce658958-2895-4b71-abec-6fb1d2097fc7",
        "ticket_ids": [
            "1d48dd2a-8ca1-4239-9227-411e31df7478",
            "fd0e3a15-c08b-4eef-952d-5c10a94f7a73",
            "94d31719-dd8b-43a7-8d11-03272a6a29a9",
            "cc7e83bd-e780-49a1-b410-865c438466b5",
            "468ec616-88f7-423a-a51c-a4d6711d6c6e",
            "8b3684fb-b909-411f-95ba-89d2d18948ab",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_9bn546--ce658958-2895-4b71-abec-6fb1d2097fc7?mode=standalone",
    },

    "yoshinoya": {
        "activity_id": "REPLACE_ME_YOSHINOYA_ACTIVITY",
        "ticket_ids": [
            "REPLACE_ME_TICKET_ID_1",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve",
    },

    "osada_sanso": {
        "activity_id": "REPLACE_ME_OSADA_ACTIVITY",
        "ticket_ids": [
            "REPLACE_ME_TICKET_ID_1",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4",
    },

    "higashi_fuji_sanso": {
        "activity_id": "REPLACE_ME_HIGASHI_ACTIVITY",
        "ticket_ids": [
            "REPLACE_ME_TICKET_ID_1",
            # ...
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap",
    },
}

# NOTE: fuji_mountain_guides intentionally removed.

PEEK_BASE = "https://book.peek.com/services/api"

# --- Helpers -----------------------------------------------------------------

def peek_headers(referer: str) -> dict:
    """Headers that make Peek return JSON reliably."""
    return {
        "Accept": "application/vnd.api+json, application/json;q=0.9, */*;q=0.8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": referer or "https://book.peek.com/",
        "Origin": "https://book.peek.com",
        "Connection": "keep-alive",
    }

def build_times_url(date_iso: str) -> str:
    return f"{PEEK_BASE}/availability-dates/{date_iso}/availability-times"

def query_peek_for_date(hut_key: str, date_iso: str):
    """
    Call Peek once per date with all ticket_ids for this hut.
    If any timeslot shows available spots, return a list of (time, spots).
    """
    cfg = HUTS.get(hut_key)
    if not cfg:
        return {"ok": False, "error": f"Unknown hut: {hut_key}"}

    activity_id = cfg.get("activity_id")
    ticket_ids = cfg.get("ticket_ids") or []
    if not activity_id or not ticket_ids or "REPLACE_ME" in activity_id or any("REPLACE_ME" in t for t in ticket_ids):
        return {"ok": False, "error": f"Missing real IDs for '{hut_key}'. Fill activity_id & ticket_ids."}

    # Build params: activity + multiple tickets array
    params = [("activity_id", activity_id)]
    # Using a random UUID for src_booking_refid is fine; Peek accepts it.
    params.append(("src_booking_refid", str(uuid.uuid4())))
    for i, tid in enumerate(ticket_ids):
        params.append((f"tickets[{i}][quantity]", "1"))
        params.append((f"tickets[{i}][ticket_id]", tid))

    url = build_times_url(date_iso)
    try:
        resp = requests.get(url, headers=peek_headers(cfg.get("referer", "")), params=params, timeout=25)
    except Exception as e:
        return {"ok": False, "error": f"HTTP error for {hut_key} {date_iso}: {e}"}

    # Some endpoints may redirect; requests follows redirects by default.
    if resp.status_code != 200:
        return {"ok": False, "error": f"Status {resp.status_code} for {hut_key} on {date_iso}"}

    # Parse JSON
    try:
        payload = resp.json()
    except Exception:
        # Sometimes Peek returns HTML shell if headers are off; we guard against that.
        return {"ok": False, "error": f"Non-JSON response for {hut_key} on {date_iso}"}

    data = payload.get("data") or []
    found = []
    for item in data:
        attrs = (item.get("attributes") or {})
        mode = attrs.get("availability-mode")
        availability = attrs.get("availability") or []
        # If mode says "available" and any option has spots_left > 0 -> we consider available
        if mode == "available":
            # sum all spots_left we see (across ticket/resource options)
            total_spots = 0
            for opt in availability:
                try:
                    total_spots += int(opt.get("spots_left", 0) or 0)
                except Exception:
                    pass
            # Accept "available" even if spots_left missing but "spots" key exists
            if total_spots <= 0:
                try:
                    total_spots = int(attrs.get("spots", 0) or 0)
                except Exception:
                    pass
            time_str = attrs.get("time") or ""
            if total_spots > 0:
                found.append((time_str, total_spots))

    return {"ok": True, "available": found}

def send_email(to_email, hut_key, found_dates):
    subject = f"⛺ {hut_key.replace('_', ' ').title()} — Availability Alert"
    lines = [
        "Hello,",
        "",
        f"The following dates now have availability for {hut_key.replace('_', ' ').title()}:",
        "",
    ]
    for date_iso, slots in found_dates:
        # slots is a list of (time, spots) tuples
        if slots:
            time_s = ", ".join([f"{t} ({s} spot{'s' if s!=1 else ''})" for t, s in slots])
            lines.append(f"  • {date_iso}: {time_s}")
        else:
            lines.append(f"  • {date_iso}: available (spots shown at checkout)")

    lines += [
        "",
        "Book ASAP to secure your spot!",
    ]
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        print(f"✅ Alert sent to {to_email} for {hut_key}")

# --- Main --------------------------------------------------------------------

def main():
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, sslmode="require"
    )
    cur = conn.cursor()
    cur.execute("SELECT email, hut, start_date, end_date FROM subscriptions")
    subs = cur.fetchall()
    print(f"🔍 Found {len(subs)} subscriptions")

    for email, hut_key, start_date, end_date in subs:
        if hut_key not in HUTS:
            print(f"⚠️ Hut '{hut_key}' not configured. Skipping {email}.")
            continue

        cfg = HUTS[hut_key]
        if not cfg.get("activity_id") or not cfg.get("ticket_ids") or "REPLACE_ME" in cfg.get("activity_id", "") \
           or any("REPLACE_ME" in t for t in cfg.get("ticket_ids", [])):
            print(f"⚠️ Missing IDs for '{hut_key}'. Fill activity_id and ticket_ids. Skipping {email}.")
            continue

        print(f"➡️ Checking {email}, hut: {hut_key}, from {start_date} to {end_date}")

        d = start_date
        matches = []
        while d <= end_date:
            iso = d.strftime("%Y-%m-%d")
            res = query_peek_for_date(hut_key, iso)
            if not res.get("ok"):
                print(f"   ⚠️ {iso}: {res.get('error')}")
            else:
                avail = res.get("available") or []
                if avail:
                    matches.append((iso, avail))
                else:
                    print(f"   ❌ {iso}: no spots")
            d += timedelta(days=1)

        if matches:
            send_email(email, hut_key, matches)
        else:
            print(f"❌ No availability for {email} on requested dates")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
