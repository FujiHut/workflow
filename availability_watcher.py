import os
import uuid
import time
from datetime import timedelta
import psycopg2
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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

# ==============================
# Huts Configuration
# ==============================
HUTS = {
    "taiyokan": [
        ("Taiyokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB")
    ],
    "kamaiwakan": [
        ("Dormitory", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_ajabkj--2d5843d4-e181-468a-bf96-9a5a4bac08cd?mode=standalone"),
        ("Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_pr85x8--959b0b5d-02da-4b6b-880b-ce09023357eb?mode=standalone"),
        ("Private Double Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_68v53j--c9632f5a-1245-466d-b14e-701d9c4f8aee?mode=standalone"),
        ("Loft", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_r4n5xq--d009aab7-6cc6-4ba5-a814-92c8bb8b1771?mode=standalone"),
        ("Private Capsule Sunrise View", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_49repp--250aa6d9-0ed1-4e94-a4fc-1e97f0922fc2?mode=standalone"),
        ("Private Room", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_jxyq9z--e1645fb8-e20c-46d7-b23e-e4732cd663a6?mode=standalone")
    ],
    "setokan": [
        ("Setokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_9bn546--ce658958-2895-4b71-abec-6fb1d2097fc7?mode=standalone")
    ],
    "miharashikan": [
        ("Miharashikan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone")
    ],
    "yamaguchiya": [
        ("Yamaguchiya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me")
    ],
    "yoshinoya": [
        ("Yoshinoya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve")
    ],
    "osada_sanso": [
        ("Osada Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4")
    ],
    "higashi_fuji_sanso": [
        ("Higashi Fuji Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap")
    ],
}

# ==============================
# Selenium driver setup helper
# ==============================
def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ==============================
# Query day logic using Selenium scraping
# ==============================
def query_day(hut_key: str, date_iso: str):
    if hut_key not in HUTS:
        return {"ok": False, "error": f"Hut '{hut_key}' not configured"}

    results = []

    for room_name, url in HUTS[hut_key]:
        driver = create_driver()
        try:
            driver.get(url)

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-app-calendar-month-day]"))
            )

            day_elements = driver.find_elements(By.CSS_SELECTOR, "[data-app-calendar-month-day]")

            for elem in day_elements:
                day_date = elem.get_attribute("data-app-calendar-month-day")
                if day_date != date_iso:
                    continue

                try:
                    calendar_day_div = elem.find_element(By.CSS_SELECTOR, "div.calendar-day")
                    classes = calendar_day_div.get_attribute("class")
                    if "has-availability" in classes:
                        results.append((f"{room_name}", ("", 1)))
                        print(f"✅ {hut_key} {room_name} {date_iso} is AVAILABLE")
                    else:
                        print(f"❌ {hut_key} {room_name} {date_iso} is NOT available")
                except Exception as e:
                    print(f"⚠️ Error reading day element for {hut_key} {room_name} {date_iso}: {e}")
        except Exception as e:
            print(f"⚠️ Error loading page for {hut_key} {room_name}: {e}")
        finally:
            driver.quit()

    return {"ok": True, "available": results}

# ==============================
# Send email
# ==============================
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

    for email, hut_key, start_date, end_date in subs:
        if hut_key not in HUTS:
            print(f"⚠️ Hut '{hut_key}' not configured, skipping {email}.")
            continue

        print(f"➡️ Checking {email}, hut: {hut_key}, from {start_date} to {end_date}")

        d = start_date
        matches = []
        while d <= end_date:
            iso = d.strftime("%Y-%m-%d")
            result = query_day(hut_key, iso)
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
