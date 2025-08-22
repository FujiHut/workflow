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

PEEK_API_KEY = "9846cbab-98f5-477d-b7d1-1ab5928778ff"
PEEK_BASE = "https://book.peek.com/services/api"

# ==============================
# Huts Configuration (with activity/ticket IDs)
# ==============================
HUTS = {
    "kamaiwakan": {
        "activity_id": "7d7d64c6-f3e8-44a9-a214-76c938db3a8f",
        "ticket_ids": [
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
        "ticket_ids": ["ef97a7a5-98d5-49f0-aef0-4e1939b3bca3"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB",
    },
    "miharashikan": {
        "activity_id": "82acdcf2-56f3-4934-8f0b-3e12f4d2781c",
        "ticket_ids": ["27e3a4f0-b199-4cf3-a4de-c9163f69a9d9"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone",
    },
    "yamaguchiya": {
        "activity_id": "f41201c6-2b4f-4d2a-b927-93a2c65a8221",
        "ticket_ids": ["a81399f2-7881-44a3-b9d7-c8cba34e52ac"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me",
    },
    "yoshinoya": {
        "activity_id": "299d662c-33d7-46d0-99b0-4f5dbb991690",
        "ticket_ids": ["ba1b80f7-6a4f-4e47-92a3-9dbd9e9c8e15"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve",
    },
    "osada_sanso": {
        "activity_id": "299d662c-33d7-46d0-99b0-4f5dbb991690",
        "ticket_ids": ["ba1b80f7-6a4f-4e47-92a3-9dbd9e9c8e15"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4",
    },
    "higashi_fuji_sanso": {
        "activity_id": "13c7a6aa-26f0-4726-a0ab-2c799de0f1d4",
        "ticket_ids": ["7e8f2d40-6d88-4e24-a0b8-17d9e637b631"],
        "referer": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap",
    },
}

# ==============================
# Helpers
# ==============================
def base_headers(referer: str) -> dict:
    return {
        "Accept": "application/vnd.api+json, application/json;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Origin": "https://book.peek.com",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        "Authorization": f"Key {PEEK_API_KEY}",
    }

def warm_up_session(session: requests.Session, referer: str):
    try:
        r = session.get(
            referer,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
            allow_redirects=True,
        )
        time.sleep(0.5)
        return r.status_code
    except Exception as e:
        print(f"⚠️ Warm-up failed for {referer}: {e}")
        return None

def build_times_url(date_iso: str) -> str:
    return f"{PEEK_BASE}/availability-dates/{date_iso}/availability-times"

def query_day(session: requests.Session, hut_key: str, date_iso: str):
    cfg = HUTS[hut_key]
    activity_id = cfg["activity_id"]
    ticket_ids = cfg["ticket_ids"]
    referer = cfg["referer"]

    warm_up_session(session, referer)

    def call_api(include_refid: bool):
        params = [("activity_id", activity_id)]
        if include_refid:
            params.append(("src_booking_refid", SESSION_REFID))
        for i, tid in enumerate(ticket_ids):
            params.append((f"tickets[{i}][quantity]", "1"))
            params.append((f"tickets[{i}][ticket_id]", tid))
        url = build_times_url(date_iso)
        return session.get(url, headers=base_headers(referer), params=params, timeout=25)

    resp = call_api(include_refid=True)
    if resp.status_code == 401:
        warm_up_session(session, referer)
        resp = call_api(include_refid=False)

    time.sleep(0.5)  # prevent throttling

    if resp.status_code != 200:
        return {"ok": False, "error": f"Status {resp.status_code} for {hut_key} on {date_iso} — {resp.text[:150]}"}

    try:
        payload = resp.json()
    except:
        return {"ok": False, "error": f"Non-JSON for {hut_key} on {date_iso}"}

    found = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        if attrs.get("availability-mode") == "available":
            total_spots = sum(int(opt.get("spots_left", 0) or 0) for opt in attrs.get("availability", []))
            if total_spots <= 0:
                total_spots = int(attrs.get("spots", 0) or 0)
            if total_spots > 0:
                found.append((attrs.get("time", ""), total_spots))

    return {"ok": True, "available": found}

def send_email(to_email: str, hut_key: str, found_dates):
    subject = f"⛺ {hut_key.replace('_', ' ').title()} — Availability Alert"
    body = "Hello,\n\nThe following dates are now available:\n\n"
    for date_iso, slots in found_dates:
        slot_text = ", ".join([f"{t} ({s} spot{'s' if s != 1 else ''})" for t, s in slots])
        body += f"- {date_iso}: {slot_text}\n"
    body += "\nBook ASAP!"
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
            print(f"⚠️ Hut '{hut_key}' not configured, skipping {email}.")
            continue

        print(f"➡️ Checking {email}, hut: {hut_key}, from {start_date} to {end_date}")

        d = start_date
        matches = []
        while d <= end_date:
            iso = d.strftime("%Y-%m-%d")
            result = query_day(session, hut_key, iso)
            if not result.get("ok"):
                print(f"⚠️ {iso}: {result.get('error')}")
            else:
                avail = result.get("available", [])
                if avail:
                    matches.append((iso, avail))
                else:
                    print(f"❌ {iso}: no spots")
            d += timedelta(days=1)

        if matches:
            send_email(email, hut_key, matches)
        else:
            print(f"❌ No availability for {email}")

    cur.close()
    conn.close()

SESSION_REFID = str(uuid.uuid4())

if __name__ == "__main__":
    main()
