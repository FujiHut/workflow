import os
import time
from datetime import timedelta
import psycopg2
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    # Local/dev auto-install (keeps CI simple too)
    from webdriver_manager.chrome import ChromeDriverManager
    _USE_WDM = True
except Exception:
    _USE_WDM = False

# =================================
# Environment
# =================================
load_dotenv()
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

# =================================
# Huts + rooms (from your working checkava.py)
# NOTE: Fuji Mountain Guides removed (not a hut).
# =================================
HUTS = {
    "taiyokan": [
        ("Taiyokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB"),
    ],
    "kamaiwakan": [
        ("Dormitory", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_ajabkj--2d5843d4-e181-468a-bf96-9a5a4bac08cd?mode=standalone"),
        ("Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_pr85x8--959b0b5d-02da-4b6b-880b-ce09023357eb?mode=standalone"),
        ("Private Double Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_68v53j--c9632f5a-1245-466b-b14e-701d9c4f8aee?mode=standalone"),
        ("Loft", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_r4n5xq--d009aab7-6cc6-4ba5-a814-92c8bb8b1771?mode=standalone"),
        ("Private Capsule Sunrise View", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_49repp--250aa6d9-0ed1-4e94-a4fc-1e97f0922fc2?mode=standalone"),
        ("Private Room", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_jxyq9z--e1645fb8-e20c-46d7-b23e-e4732cd663a6?mode=standalone"),
    ],
    "setokan": [
        ("Setokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_9bn546--ce658958-2895-4b71-abec-6fb1d2097fc7?mode=standalone"),
    ],
    "miharashikan": [
        ("Miharashikan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone"),
    ],
    "yamaguchiya": [
        ("Yamaguchiya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me"),
    ],
    "yoshinoya": [
        ("Yoshinoya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve"),
    ],
    "osada_sanso": [
        ("Osada Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4"),
    ],
    "higashi_fuji_sanso": [
        ("Higashi Fuji Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap"),
    ],
}

# =================================
# Selenium setup
# =================================
def create_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")
    # Make it a bit more “browsery”
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    if _USE_WDM:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    # Fallback if ChromeDriver is preinstalled (e.g., CI)
    return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)

def wait_for_calendar(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-app-calendar-month-day]"))
    )

def ensure_date_loaded(driver, date_iso: str, tries: int = 6, pause: float = 0.6):
    """
    Some calendars lazy-load more months as you scroll.
    We try a few scrolls to reveal the target date if it's far ahead.
    """
    sel = f"[data-app-calendar-month-day='{date_iso}']"
    for _ in range(tries):
        if driver.find_elements(By.CSS_SELECTOR, sel):
            return True
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(pause)
    return bool(driver.find_elements(By.CSS_SELECTOR, sel))

def page_has_availability_for_date(driver, date_iso: str) -> bool:
    """
    Uses the same selector logic you proved works:
    - Find the element with data-app-calendar-month-day = YYYY-MM-DD
    - Check if its .calendar-day has class 'has-availability'
    """
    sel = f"[data-app-calendar-month-day='{date_iso}']"
    cells = driver.find_elements(By.CSS_SELECTOR, sel)
    for cell in cells:
        try:
            # Common structure: wrapper -> div.calendar-day
            daydiv = cell.find_element(By.CSS_SELECTOR, "div.calendar-day")
        except Exception:
            daydiv = cell  # fallback: sometimes the attribute is on the same element

        classes = (daydiv.get_attribute("class") or "").lower()
        if "has-availability" in classes or "available" in classes:
            return True
    return False

def check_room_dates(driver, hut_key: str, room_name: str, url: str, start_date, end_date):
    """
    Loads the room page and checks each date in the range.
    Returns: List[ (date_iso, True) ] for dates that are available.
    """
    found = []
    d = start_date
    while d <= end_date:
        date_iso = d.strftime("%Y-%m-%d")
        try:
            driver.get(url)
            wait_for_calendar(driver, timeout=25)

            # Try to make sure the target date is actually in the DOM (lazy load)
            ensure_date_loaded(driver, date_iso)

            if page_has_availability_for_date(driver, date_iso):
                print(f"✅ {hut_key} — {room_name} — {date_iso} is AVAILABLE")
                found.append((date_iso, room_name, url))
            else:
                print(f"   ❌ {hut_key} — {room_name} — {date_iso}: no spots")
        except Exception as e:
            print(f"   ⚠️ {hut_key} — {room_name} — {date_iso}: {e}")
        finally:
            # brief pause to be polite / avoid rate-limits
            time.sleep(0.25)
        d += timedelta(days=1)
    return found

# =================================
# Email
# =================================
def send_email(to_email: str, hut_key: str, found_rows):
    """
    found_rows: List[(date_iso, room_name, url)]
    """
    subject = f"⛺ {hut_key.replace('_', ' ').title()} — Availability Alert"
    lines = [
        "Hello,",
        "",
        f"Good news! We found availability for {hut_key.replace('_',' ').title()}:",
        "",
    ]

    # Group by date
    by_date = {}
    for date_iso, room_name, url in found_rows:
        by_date.setdefault(date_iso, []).append((room_name, url))

    for date_iso in sorted(by_date.keys()):
        lines.append(f"• {date_iso}")
        for room_name, url in by_date[date_iso]:
            lines.append(f"   - {room_name}: {url}")

    lines += ["", "Book ASAP to secure your spot."]
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        print(f"✅ Alert sent to {to_email} for {hut_key}")

# =================================
# Main
# =================================
def main():
    # Connect DB and get subscriptions
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, sslmode="require"
    )
    cur = conn.cursor()
    cur.execute("SELECT email, hut, start_date, end_date FROM subscriptions")
    subs = cur.fetchall()
    print(f"🔍 Found {len(subs)} subscriptions")

    driver = create_driver()

    try:
        for email, hut_key, start_date, end_date in subs:
            if hut_key not in HUTS:
                print(f"⚠️ Hut '{hut_key}' not configured. Skipping {email}.")
                continue

            rooms = HUTS[hut_key]
            print(f"➡️ Checking {email}, hut: {hut_key}, from {start_date} to {end_date}")

            all_found = []
            for room_name, url in rooms:
                found = check_room_dates(driver, hut_key, room_name, url, start_date, end_date)
                all_found.extend(found)

            if all_found:
                send_email(email, hut_key, all_found)
            else:
                print(f"❌ No availability for {email} on requested dates for {hut_key}")
    finally:
        driver.quit()
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
