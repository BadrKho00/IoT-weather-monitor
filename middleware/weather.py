import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = os.getenv("CITY")
COUNTRY_CODE = os.getenv("COUNTRY_CODE")


def get_current_weather():
    if not API_KEY:
        return {
            "temperature_outdoor": None,
            "humidity_outdoor": None,
            "weather_description": "API key not set",
            "wind_speed": None,
            "weather_icon": "01d"
        }
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": f"{CITY},{COUNTRY_CODE}",
        "appid": API_KEY,
        "units": "metric"
    }
    response = requests.get(url, params=params)
    data = response.json()
    return {
        "temperature_outdoor": data["main"]["temp"],
        "humidity_outdoor": data["main"]["humidity"],
        "weather_description": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"]
    }


def get_forecast():
    if not API_KEY:
        return []
    url = "http://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": f"{CITY},{COUNTRY_CODE}",
        "appid": API_KEY,
        "units": "metric",
        "cnt": 7
    }
    response = requests.get(url, params=params)
    data = response.json()
    forecast = []
    for item in data["list"]:
        forecast.append({
            "datetime": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "description": item["weather"][0]["description"],
            "icon": item["weather"][0]["icon"]
        })
    return forecast