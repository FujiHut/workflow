import os
import psycopg2
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load environment variables
load_dotenv()
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

HUT_URLS = {
    "kamaiwakan": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/vP9OM",
    "taiyokan": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/ZYLbB",
    "miharashikan": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_y83bej--a732d212-bdb2-49c9-afee-3cb1a8b7c6b7?mode=standalone",
    "yamaguchiya": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/dy9Me",
    "setokan": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_9bn546--ce658958-2895-4b71-abec-6fb1d2097fc7?mode=standalone",
    "yoshinoya": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/l7Wve",
    "osada_sanso": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/rb3b4",
    "higashi_fuji_sanso": "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/8aMap",
    "fuji_mountain_guides": "https://www.fujimountainguides.com/two-day-mt-fuji-tour.html"
}

# Configure Chrome options
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# ✅ Different setup depending on environment
if os.getenv("GITHUB_ACTIONS"):  # Running inside GitHub Actions
    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
else:  # Local dev
    from webdriver_manager.chrome import ChromeDriverManager
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def send_email(to_email, hut, found_dates):
    subject = "⛺ {} Availability Alert".format(hut.replace("_", " ").title())
    body = "Hello,\n\n"
    body += "The following dates are now available for {}:\n\n".format(hut.replace("_", " ").title())
    body += "\n".join(found_dates)
    body += "\n\nBook ASAP to secure your spot!"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)
        print("✅ Alert sent to {} for {}: {}".format(to_email, hut, found_dates))


def check_availability(hut, hut_url, date_iso):
    try:
        driver.get(hut_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div"))
        )
        page = driver.page_source
        soup = BeautifulSoup(page, "html.parser")

        # Look for date text on the page
        return date_iso in soup.get_text()
    except Exception as e:
        print(f"⚠️ Error checking {hut_url}: {e}")
        return False


def main():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        sslmode="require"
    )
    cur = conn.cursor()
    cur.execute("SELECT email, hut, start_date, end_date FROM subscriptions")
    subs = cur.fetchall()
    print("🔍 Found {} subscriptions".format(len(subs)))

    for email, hut, start_date, end_date in subs:
        print(f"➡️ Checking for {email}, hut: {hut}, from {start_date} to {end_date}")
        hut_url = HUT_URLS.get(hut)
        if not hut_url:
            print(f"⚠️ No URL for hut: {hut}, skipping.")
            continue

        current = start_date
        matches = []

        while current <= end_date:
            iso = current.strftime("%Y-%m-%d")
            print("  📅 Checking", iso)

            if check_availability(hut, hut_url, iso):
                matches.append(iso)
            current += timedelta(days=1)

        if matches:
            send_email(email, hut, matches)
        else:
            print("❌ No availability found for {}".format(email))

    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        driver.quit()
