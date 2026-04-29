import requests
import random
import time
from datetime import datetime

MIDDLEWARE_URL = "http://127.0.0.1:5000/data"
INTERVAL_SECONDS = 10


def generate_sensor_data():
    return {
        "temperature_indoor": round(random.uniform(18.0, 26.0), 1),
        "humidity_indoor": round(random.uniform(30.0, 70.0), 1),
        "air_quality": random.randint(50, 300),
        "motion_detected": random.choice([True, False])
    }


if __name__ == "__main__":
    print(f"Simulator started — sending data every {INTERVAL_SECONDS}s")
    print(f"Target: {MIDDLEWARE_URL}")
    print("-" * 40)

    while True:
        data = generate_sensor_data()
        try:
            r = requests.post(MIDDLEWARE_URL, json=data)
            response = r.json()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent: {data}")
            if response.get("alerts"):
                print(f"  ALERTS: {response['alerts']}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
        time.sleep(INTERVAL_SECONDS)