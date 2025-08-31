import os
import uuid
import time
from datetime import datetime, timedelta
import psycopg2
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import logging

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
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
# Logging setup
# ==============================
LOG_DIR = os.path.dirname(__file__)
AVAIL_LOG_FILE = os.path.join(LOG_DIR, "availability_log.txt")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error_log.txt")

# Remove old log files to keep only latest run
for f in [AVAIL_LOG_FILE, ERROR_LOG_FILE]:
    if os.path.exists(f):
        os.remove(f)

# Configure loggers
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
avail_logger = logging.getLogger("availability")
avail_handler = logging.FileHandler(AVAIL_LOG_FILE)
avail_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', '%Y-%m-%d %H:%M:%S'))
avail_logger.addHandler(avail_handler)
avail_logger.propagate = False

error_logger = logging.getLogger("errors")
error_handler = logging.FileHandler(ERROR_LOG_FILE)
error_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', '%Y-%m-%d %H:%M:%S'))
error_logger.addHandler(error_handler)
error_logger.propagate = False

# To filter duplicate log lines in a single run
seen_messages = set()
def log_avail(msg):
    if msg not in seen_messages:
        avail_logger.info(msg)
        print(msg)
        seen_messages.add(msg)

def log_error(msg):
    error_logger.error(msg)
    print(f"❌ {msg}")

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
# Scrape full calendar for available dates (with retries)
# ==============================
def scrape_calendar(url, room_name="Default", max_retries=3):
    driver = create_driver()
    driver.get(url)
    
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-app-calendar-month-day]"))
        )
    except:
        log_avail(f"⚠️ Calendar not loaded for {room_name}")
        driver.quit()
        return []

    available_dates = []
    seen_months = set()
    retries = 0

    while True:
        try:
            day_elements = driver.find_elements(By.CSS_SELECTOR, "[data-app-calendar-month-day]")
            for elem in day_elements:
                try:
                    date_str = elem.get_attribute("data-app-calendar-month-day")
                    if not date_str:
                        continue
                    day_div = elem.find_element(By.CSS_SELECTOR, "div.calendar-day")
                    classes = day_div.get_attribute("class")
                    if "has-availability" in classes:
                        available_dates.append((date_str, room_name))
                        log_avail(f"✅ {room_name} {date_str} available")
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    log_avail(f"⚠️ Error reading day {date_str} for {room_name}: {e}")

            month_text = driver.find_element(By.CSS_SELECTOR, ".month-title-text").text.strip()
            if month_text in seen_months:
                break
            seen_months.add(month_text)

            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "span.pro-form-icon.pro-icon-position-left")
                next_btn.click()
                time.sleep(1)
            except NoSuchElementException:
                break

        except StaleElementReferenceException:
            if retries < max_retries:
                retries += 1
                time.sleep(1)
                continue
            else:
                log_avail(f"⚠️ Too many stale element errors for {room_name}")
                break

    driver.quit()
    return available_dates

# ==============================
# Send aggregated email
# ==============================
def send_email(to_email: str, availability_dict):
    subject = "⛺ Mount Fuji Hut Availability Alert"
    body = "Hello,\n\nThe following dates are now available:\n\n"
    for hut_key, dates in availability_dict.items():
        body += f"{hut_key.replace('_', ' ').title()}:\n"
        for date, room in dates:
            body += f"  - {date}: {room}\n"
    body += "\nBook ASAP!"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        log_avail(f"✅ Email sent to {to_email}")

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
    log_avail(f"🔍 Found {len(subs)} subscriptions")

    for email, hut_key, start_date, end_date in subs:
        if hut_key not in HUTS:
            log_avail(f"⚠️ Hut '{hut_key}' not configured, skipping {email}")
            continue

        availability_dict = {}
        log_avail(f"➡️ Checking availability for {email} (hut: {hut_key})")

        for room_name, url in HUTS[hut_key]:
            dates = scrape_calendar(url, room_name)

            # Convert scraped string dates to datetime.date
            parsed_dates = []
            for date_str, room in dates:
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    parsed_dates.append((date_obj, room))
                except Exception as e:
                    log_avail(f"⚠️ Failed to parse date {date_str} for {room_name}: {e}")

            # Filter by user date range
            filtered_dates = [d for d in parsed_dates if start_date <= d[0] <= end_date]

            if filtered_dates:
                availability_dict.setdefault(hut_key, []).extend(filtered_dates)

        if availability_dict:
            send_email(email, availability_dict)
        else:
            log_avail(f"❌ No availability for {email}")

    cur.close()
    conn.close()

# ==============================
# Run main with crash logging
# ==============================
SESSION_REFID = str(uuid.uuid4())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        log_error(error_details)
