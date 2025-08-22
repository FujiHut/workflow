import os
import uuid
import time
from datetime import timedelta
import psycopg2
import requests
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv

# ==============================
# Environment
# ==============================
load_dotenv()
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

HUTS = {
    # KAMAIWAKAN — 6 separate room types (replace with your real IDs)
    "kamaiwakan": {
        "activity_id": "7d7d64c6-f3e8-44a9-a214-76c938db3a8f",
        "ticket_ids": [
            # Paste all 6 ticket_ids you extracted for Kamaiwakan
            "7c1d9a26-b6f0-4e39-b2fb-f0f6b6a9a8f1",
            "64f74c28-9ad3-4657-b2f4-b3e511e2aa26",
            "efc7c58c-83fa-4b54-9860-16c02172df87",
            "0e7b6b5e-f31d-4b24-9f2f-d1a6c6634a7e",
            "9c2bfa3f-7c26-4e7c-b35c-fb6a87d7f731",
            "bdc1c9d7-29af-4621-a927-6f9638ac9321",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/vP9OM",
    },
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
    "taiyokan": {
        "activity_id": "c13b9a91-6a32-4e3e-905a-3c2f26df9f72",
        "ticket_ids": [
            # Add all ticket_ids you saw in the JSON
            "ef97a7a5-98d5-49f0-aef0-4e1939b3bca3",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB",
    },

    "miharashikan": {
        "activity_id": "82acdcf2-56f3-4934-8f0b-3e12f4d2781c",
        "ticket_ids": [
            "27e3a4f0-b199-4cf3-a4de-c9163f69a9d9",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone",
    },

    "yamaguchiya": {
        "activity_id": "f41201c6-2b4f-4d2a-b927-93a2c65a8221",
        "ticket_ids": [
            "a81399f2-7881-44a3-b9d7-c8cba34e52ac",
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
        "activity_id": "299d662c-33d7-46d0-99b0-4f5dbb991690",
        "ticket_ids": [
            "ba1b80f7-6a4f-4e47-92a3-9dbd9e9c8e15",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve",
    },

    "osada_sanso": {
        "activity_id": "299d662c-33d7-46d0-99b0-4f5dbb991690",
        "ticket_ids": [
            "ba1b80f7-6a4f-4e47-92a3-9dbd9e9c8e15",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4",
    },

    "higashi_fuji_sanso": {
        "activity_id": "13c7a6aa-26f0-4726-a0ab-2c799de0f1d4",
        "ticket_ids": [
            "7e8f2d40-6d88-4e24-a0b8-17d9e637b631",
        ],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap",
    },
}

# NOTE: fuji_mountain_guides intentionally removed.

PEEK_BASE = "https://book.peek.com/services/api"


# ==============================
# HTTP Session & Headers
# ==============================
def base_headers(referer: str) -> dict:
    # Browser-y headers. Keep Referer exact to the booking page for this hut.
    return {
        "Accept": "application/vnd.api+json, application/json;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": referer or "https://book.peek.com/",
        "Origin": "https://book.peek.com",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        # "Content-Type" not needed for GET
    }

def warm_up_session(session: requests.Session, referer: str):
    """
    Load the booking page to set same-origin cookies (prevents 401).
    """
    try:
        r = session.get(
            referer,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Referer": "https://book.peek.com/",
                "Connection": "keep-alive",
            },
            timeout=20,
            allow_redirects=True,
        )
        # A short pause helps when CF or app sets cookies asynchronously
        time.sleep(0.5)
        return r.status_code
    except Exception as e:
        print(f"   ⚠️ Warm-up failed for referer: {referer}: {e}")
        return None

def build_times_url(date_iso: str) -> str:
    return f"{PEEK_BASE}/availability-dates/{date_iso}/availability-times"

def query_day(session: requests.Session, hut_key: str, date_iso: str):
    """
    Query Peek for this hut/date.
    Tries with src_booking_refid first, then without if 401.
    Returns dict: {ok: bool, available: [(time, spots), ...]} OR {ok: False, error: "..."}
    """
    cfg = HUTS[hut_key]
    activity_id = cfg["activity_id"]
    ticket_ids = cfg["ticket_ids"]
    referer = cfg["referer"]

    # Warm up the session to get cookies
    warm_up_session(session, referer)

    def call_api(include_refid: bool):
        params = [("activity_id", activity_id)]
        if include_refid:
            # stable per run is fine
            params.append(("src_booking_refid", SESSION_REFID))
        # include ALL tickets with quantity=1 (we just need availability)
        for i, tid in enumerate(ticket_ids):
            params.append((f"tickets[{i}][quantity]", "1"))
            params.append((f"tickets[{i}][ticket_id]", tid))

        url = build_times_url(date_iso)
        resp = session.get(url, headers=base_headers(referer), params=params, timeout=25)
        return resp

    # 1) Try with src_booking_refid
    resp = call_api(include_refid=True)

    # If 401, try without src_booking_refid (some experiences require none)
    if resp.status_code == 401:
        # Re-warm the session (sometimes needed for certain huts) then retry
        warm_up_session(session, referer)
        resp = call_api(include_refid=False)

    if resp.status_code != 200:
        preview = (resp.text or "")[:160].replace("\n", " ")
        return {
            "ok": False,
            "error": f"Status {resp.status_code} for {hut_key} on {date_iso} — {preview}",
        }

    try:
        payload = resp.json()
    except Exception:
        preview = (resp.text or "")[:160].replace("\n", " ")
        return {"ok": False, "error": f"Non-JSON for {hut_key} on {date_iso} — {preview}"}

    data = payload.get("data") or []
    found = []
    for item in data:
        attrs = item.get("attributes") or {}
        mode = attrs.get("availability-mode")
        availability = attrs.get("availability") or []
        # Accept "available" as signal and add up any spots we can see
        if mode == "available":
            total = 0
            for opt in availability:
                try:
                    total += int(opt.get("spots_left", 0) or 0)
                except Exception:
                    pass
            if total <= 0:
                try:
                    total = int(attrs.get("spots", 0) or 0)
                except Exception:
                    pass
            if total > 0:
                found.append((attrs.get("time") or "", total))

    return {"ok": True, "available": found}

def send_email(to_email: str, hut_key: str, found_dates):
    subject = f"⛺ {hut_key.replace('_', ' ').title()} — Availability Alert"
    lines = [
        "Hello,",
        "",
        f"The following dates have availability for {hut_key.replace('_', ' ').title()}:",
        "",
    ]
    for date_iso, slots in found_dates:
        if slots:
            time_s = ", ".join([f"{t} ({s} spot{'s' if s!=1 else ''})" for t, s in slots])
            lines.append(f"  • {date_iso}: {time_s}")
        else:
            lines.append(f"  • {date_iso}: available (spots shown at checkout)")
    lines += ["", "Book ASAP to secure your spot!"]
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        print(f"✅ Alert sent to {to_email} for {hut_key}")

# ==============================
# Main
# ==============================
def main():
    missing = [
        k for k, cfg in HUTS.items()
        if not cfg.get("activity_id") or not cfg.get("ticket_ids") or "REPLACE_ME" in cfg.get("activity_id", "") \
           or any("REPLACE_ME" in t for t in cfg.get("ticket_ids", []))
    ]
    if missing:
        print("⚠️ These huts are missing real IDs and will be skipped:", ", ".join(missing))

    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, sslmode="require"
    )
    cur = conn.cursor()
    cur.execute("SELECT email, hut, start_date, end_date FROM subscriptions")
    subs = cur.fetchall()
    print(f"🔍 Found {len(subs)} subscriptions")

    session = requests.Session()

    for email, hut_key, start_date, end_date in subs:
        if hut_key not in HUTS:
            print(f"⚠️ Hut '{hut_key}' not configured. Skipping {email}.")
            continue
        cfg = HUTS[hut_key]
        if hut_key in missing:
            print(f"⚠️ Skipping {email} — IDs not set for '{hut_key}'.")
            continue

        print(f"➡️ Checking {email}, hut: {hut_key}, from {start_date} to {end_date}")

        d = start_date
        matches = []
        while d <= end_date:
            iso = d.strftime("%Y-%m-%d")
            result = query_day(session, hut_key, iso)
            if not result.get("ok"):
                print(f"   ⚠️ {iso}: {result.get('error')}")
            else:
                avail = result.get("available") or []
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

# Stable per-run booking refid (some huts behave better with a consistent value)
SESSION_REFID = str(uuid.uuid4())

if __name__ == "__main__":
    main()
