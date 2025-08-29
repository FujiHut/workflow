import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
        ("Private Double Capsule", "https://book.peek.com/s/9846cbab-98f5-477d-b7d1-1ab5928778ff/p_68v53j--c9632f5a-1245-466b-b14e-701d9c4f8aee?mode=standalone"),
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
# Selenium Driver Setup
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
# Check availability on a given date for one hut
# ==============================
def check_availability(hut_key, room_name, url, date_iso):
    driver = create_driver()
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-app-calendar-month-day]"))
        )
        elements = driver.find_elements(By.CSS_SELECTOR, "[data-app-calendar-month-day]")

        for elem in elements:
            if elem.get_attribute("data-app-calendar-month-day") == date_iso:
                try:
                    day_div = elem.find_element(By.CSS_SELECTOR, "div.calendar-day")
                    if "has-availability" in day_div.get_attribute("class"):
                        print(f"✅ {hut_key} — {room_name} — {date_iso} is AVAILABLE")
                        return True
                except Exception as e:
                    print(f"⚠️ Error checking day element for {hut_key}: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Error loading page for {hut_key} — {room_name}: {e}")
        return False
    finally:
        driver.quit()

# ==============================
# Main logic
# ==============================
def main():
    days_ahead = 14
    today = datetime.today()
    date_list = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_ahead)]

    for hut_key, rooms in HUTS.items():
        print(f"\n🔍 Checking hut: {hut_key}")
        for room_name, url in rooms:
            for date_iso in date_list:
                check_availability(hut_key, room_name, url, date_iso)

if __name__ == "__main__":
    main()
