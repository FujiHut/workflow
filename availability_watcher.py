import os
import time
import uuid
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
    "taiyokan": [("Taiyokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB")],
    "kamaiwakan": [
        ("Dormitory", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_ajabkj--2d5843d4-e181-468a-bf96-9a5a4bac08cd?mode=standalone"),
        ("Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_pr85x8--959b0b5d-02da-4b6b-880b-ce09023357eb?mode=standalone"),
        ("Private Double Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_68v53j--c9632f5a-1245-466d-b14e-701d9c4f8aee?mode=standalone"),
        ("Loft", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_r4n5xq--d009aab7-6cc6-4ba5-a814-92c8bb8b1771?mode=standalone"),
        ("Private Capsule Sunrise View", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_49repp--250aa6d9-0ed1-4e94-a4fc-1e97f0922fc2?mode=standalone"),
        ("Private Room", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_jxyq9z--e1645fb8-e20c-46d7-b23e-e4732cd663a6?mode=standalone")
    ],
    "setokan": [("Setokan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_9bn546--ce658958-2895-4b71-abec-6fb1d2097fc7?mode=standalone")],
    "miharashikan": [("Miharashikan Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone")],
    "yamaguchiya": [("Yamaguchiya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me")],
    "yoshinoya": [("Yoshinoya Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve")],
    "osada_sanso": [("Osada Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4")],
    "higashi_fuji_sanso": [("Higashi Fuji Sanso Default", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap")],
}

# ==============================
# Selenium driver setup
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
# Navigate calendar to ensure date is visible
# ==============================
def navigate_to_month(driver, target_date):
    """Click next/back arrows until the target month is visible"""
    target_month = target_date.strftime("%B %Y")
    for _ in range(12):  # max 12 clicks
        visible_months = driver.find_elements(By.CSS_SELECTOR, ".calendar-header__month")
        if any(target_month in m.text for m in visible_months):
            return True
        # Try clicking "previous month" then "next month"
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, ".calendar-header__next")
            next_btn.click()
        except:
            pass
        time.sleep(0.5)
    return False

# ==============================
# Query day for a hut and room
# ==============================
def query_day(driver, url, date_iso):
    driver.get(url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-app-calendar-month-day]"))
        )
    except:
        return False

    # Ensure month containing date is visible
    from datetime import datetime
    target_date = datetime.strptime(date_iso, "%Y-%m-%d")
    navigate_to_month(driver, target_date)

    day_elements = driver.find_elements(By.CSS_SELECTOR, "[data-app-calendar-month-day]")
    for elem in day_elements:
        day_date = elem.get_attribute("data-app-calendar-month-day")
        if day_date != date_iso:
            continue
        try:
            calendar_day_div = elem.find_element(By.CSS_SELECTOR, "div.calendar-day")
            classes = calendar_day_div.get_attribute("class")
            if "has-availability" in classes or "available" in classes.lower():
                return True
        except:
            continue
    return False

# ==============================
# Send aggregated email
# ==============================
def send_email(to_email, results):
    subject = "⛺ Mount Fuji Hut Availability Alert"
    body = "Hello,\n\nThe following huts have available dates:\n\n"
    for hut, dates in results.items():
        body += f"{hut.replace('_', ' ').title()}:\n"
        for d in dates:
            body += f"- {d}\n"
        body += "\n"
    body += "Book ASAP!"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        print(f"✅ Email sent to {to_email}")

# ==============================
# Main logic
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
            print(f"⚠️ Hut '{hut_key}' not configured, skipping {email}")
            continue

        print(f"➡️ Checking {email}, hut: {hut_key}")
        available_dates = []
        driver = create_driver()

        for room_name, url in HUTS[hut_key]:
            d = start_date
            while d <= end_date:
                iso = d.strftime("%Y-%m-%d")
                if query_day(driver, url, iso):
                    available_dates.append(f"{room_name}: {iso}")
                    print(f"✅ {hut_key} {room_name} {iso} available")
                d += timedelta(days=1)

        driver.quit()

        if available_dates:
            send_email(email, {hut_key: available_dates})
        else:
            print(f"❌ No availability for {email} at {hut_key}")

    cur.close()
    conn.close()

SESSION_REFID = str(uuid.uuid4())

if __name__ == "__main__":
    main()
