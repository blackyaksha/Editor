import json
import time
import threading
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ✅ FastAPI Web App
app = FastAPI(title="Flood Data Scraper API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

SENSOR_DATA_FILE = "sensor_data.json"
CSV_FILE_PATH = "sensor_data.csv"

# ✅ New Category for the New Sensor Type
SENSOR_CATEGORIES = {
    "rain_gauge": [
        "QCPU", "Masambong", "Batasan Hills", "Ugong Norte", "Ramon Magsaysay HS",
        "UP Village", "Dona Imelda", "Kaligayahan", "Emilio Jacinto Sr HS", "Payatas ES",
        "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit", "Libis",
        "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa",
        "Brgy Fairview (REC)", "Brgy Baesa Hall", "Brgy N.S Amoranto Hall", "Brgy Valencia Hall"
    ],
    "flood_sensors": [
        "North Fairview", "Batasan-San Mateo", "Bahay Toro", "Sta Cruz", "San Bartolome"
    ],
    "street_flood_sensors": [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    "flood_risk_index": [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    "earthquake_sensors": ["QCDRRMO", "QCDRRMO REC"],
    "new_sensor_category": [  # The new category you want to add
        "New Sensor 1", "New Sensor 2", "New Sensor 3"
    ]
}

def setup_chrome_driver():
    """Setup Chrome WebDriver with proper options and error handling"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Use new headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--disable-features=NetworkService")
        chrome_options.add_argument("--disable-features=NetworkServiceInProcess")
        chrome_options.add_argument("--disable-features=NetworkServiceInProcess2")
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
        chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-accelerated-video-encode")
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-webgl2")
        chrome_options.add_argument("--disable-3d-apis")
        
        # Initialize ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(30)
        
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
        raise

def wait_for_page_load(driver, url, max_retries=3):
    """Wait for page to load with retry logic"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} to load page: {url}")
            driver.get(url)
            
            # Wait for the table to load
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)  # Wait before retrying
    return False

# ✅ Function to Scrape All Data from iRiseUP Website
def scrape_sensor_data():
    driver = None
    try:
        logger.info("Initializing Chrome WebDriver...")
        driver = setup_chrome_driver()
        
        url = "https://app.iriseup.ph/sensor_networks"
        logger.info(f"🌍 Fetching data from: {url}")
        
        # Use the new wait_for_page_load function
        if not wait_for_page_load(driver, url):
            raise TimeoutError("Failed to load page after multiple attempts")

        sensor_data = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")

            if len(cols) >= 5:
                sensor_name = cols[0].text.strip()
                location = cols[1].text.strip()
                current_level = cols[3].text.strip()
                normal_level = cols[2].text.strip()
                description = cols[4].text.strip() if len(cols) > 4 else "N/A"

                sensor_data.append({
                    "SENSOR NAME": sensor_name,
                    "OBS TIME": location,
                    "NORMAL LEVEL": normal_level,
                    "CURRENT": current_level,
                    "DESCRIPTION": description
                })

        if not sensor_data:
            raise ValueError("No sensor data extracted. Check website structure.")

        logger.info(f"✅ Successfully scraped {len(sensor_data)} sensor records")

        # ✅ Save Data to CSV
        save_csv(sensor_data)

        # ✅ Convert CSV to JSON
        convert_csv_to_json()

        logger.info("✅ Sensor data updated successfully")

    except Exception as e:
        logger.error(f"❌ Scraping Failed: {str(e)}")
        raise

    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

# ✅ Save Data to CSV (Including All Columns)
def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    print("✅ CSV file saved successfully with all sensor data.")

# ✅ Convert CSV to JSON with All Data (Updated to distinguish Street Flood Sensors & Flood Risk Index)
def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)

    categorized_data = {category: [] for category in SENSOR_CATEGORIES}  

    for _, row in df.iterrows():
        sensor_name = row["SENSOR NAME"]
        current_value = row["CURRENT"]
        normal_value = row["NORMAL LEVEL"] if "NORMAL LEVEL" in df.columns else "N/A"
        description = row["DESCRIPTION"] if "DESCRIPTION" in df.columns else "N/A"

        sensor_entry = {
            "SENSOR NAME": sensor_name,
            "CURRENT": current_value,
        }

        # ✅ Check if "m" is in `CURRENT` value → Street Flood Sensor
        if "m" in str(current_value):
            category = "street_flood_sensors"
            sensor_entry["NORMAL LEVEL"] = normal_value
            sensor_entry["DESCRIPTION"] = description
        else:
            category = "flood_risk_index"

        # ✅ Append to correct category
        if sensor_name in SENSOR_CATEGORIES[category]:
            categorized_data[category].append(sensor_entry)

    # ✅ Add other categories (Rain Gauge, Flood Sensors, Earthquake Sensors)
    for category, sensors in SENSOR_CATEGORIES.items():
        if category not in ["street_flood_sensors", "flood_risk_index"]:  # ✅ Already handled above
            for sensor_name in sensors:
                matching_sensor = df[df["SENSOR NAME"].str.casefold() == sensor_name.casefold()]
                if not matching_sensor.empty:
                    normal_value = matching_sensor.iloc[0]["NORMAL LEVEL"] if "NORMAL LEVEL" in df.columns else "N/A"
                    current_value = matching_sensor.iloc[0]["CURRENT"]
                    description = matching_sensor.iloc[0]["DESCRIPTION"] if "DESCRIPTION" in df.columns else "N/A"

                    sensor_entry = {
                        "SENSOR NAME": sensor_name,
                        "CURRENT": current_value,
                    }

                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = normal_value
                        sensor_entry["DESCRIPTION"] = description

                    categorized_data[category].append(sensor_entry)
                else:
                    # ✅ Default empty structure
                    sensor_entry = {
                        "SENSOR NAME": sensor_name,
                        "CURRENT": "0.0m" if category == "street_flood_sensors" else 0.0,
                    }

                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = "N/A"
                        sensor_entry["DESCRIPTION"] = "N/A"

                    categorized_data[category].append(sensor_entry)

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)

    print("✅ JSON data structured correctly with Street Flood Sensor Check.")

# ✅ FastAPI Route
@app.get("/api/sensor-data", response_model=Dict[str, List[Dict[str, Any]]])
async def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="No valid data available yet")

# ✅ Background Scraping Thread
def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        scrape_sensor_data()
        print("⏳ Waiting 60 seconds before the next scrape...")
        time.sleep(60)

# ✅ Run FastAPI App
if __name__ == "__main__":
    import uvicorn
    
    # Start the background scraper thread
    scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
    scraper_thread.start()

    print("🚀 FastAPI running at http://127.0.0.1:5000/")
    uvicorn.run(app, host="0.0.0.0", port=5000)
