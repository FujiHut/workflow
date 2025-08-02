import os
import time
import psycopg2
from datetime import datetime, timedelta
from selenium import webdriver
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

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

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

# Selenium setup
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")

try:
    driver = webdriver.Chrome(options=options)

    def fetch_availability_kamaiwakan(driver, date_iso):
        print("🔍 Simulating Kamaiwakan availability for", date_iso)
        return date_iso == "2025-07-14"

    def fetch_availability_fuji_mountain_guides(driver, date_iso):
        print("🔍 Simulating Fuji Mountain Guides availability for", date_iso)
        return date_iso == "2025-07-14"

    def fetch_availability(hut_url, date_iso):
        print("🔍 Simulating availability for", hut_url, date_iso)
        return date_iso == "2025-07-14"

    def send_email(to_email, hut, found_dates):
        subject = f"⛺ {hut.replace('_', ' ').title()} Availability Alert"
        body = "Hello,\n\n"
        body += f"The following dates are now available for {hut.replace('_', ' ').title()}:\n\n"
        body += "\n".join(found_dates)
        body += "\n\nBook ASAP to secure your spot!"
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.send_message(msg)
            print(f"✅ Alert sent to {to_email} for {hut}: {found_dates}")

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
        print(f"🔎 Found {len(subs)} subscriptions")

        for email, hut, start_date, end_date in subs:
            print(f"➡️  Checking for {email}, hut: {hut}, from {start_date} to {end_date}")
            hut_url = HUT_URLS.get(hut)
            if not hut_url:
                print(f"⚠️  No URL for hut: {hut}, skipping.")
                continue

            current = start_date
            matches = []

            while current <= end_date:
                iso = current.strftime("%Y-%m-%d")
                print("  📅 Checking", iso)

                if hut == "kamaiwakan":
                    if fetch_availability_kamaiwakan(driver, iso):
                        matches.append(iso)
                elif hut == "fuji_mountain_guides":
                    if fetch_availability_fuji_mountain_guides(driver, iso):
                        matches.append(iso)
                else:
                    if fetch_availability(hut_url, iso):
                        matches.append(iso)
                current += timedelta(days=1)

            if matches:
                send_email(email, hut, matches)
            else:
                print(f"❌ No availability found for {email}")

        cur.close()
        conn.close()

finally:
    driver.quit()

if __name__ == "__main__":
    main()
