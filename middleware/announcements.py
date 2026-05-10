import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Training time from env var, default 18:00
TRAINING_TIME = os.getenv("TRAINING_TIME", "18:00")


def get_training_datetime_today():
    """Convert TRAINING_TIME string (e.g. '18:00') to a datetime object for today"""
    now = datetime.now()
    hour, minute = map(int, TRAINING_TIME.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def check_announcements(sensor_data: dict, forecast: list, motion_detected: bool = False, last_announcement_time: datetime = None) -> list:
    """
    Check all 6 announcement rules and return a list of messages to announce.

    Args:
        sensor_data: latest sensor reading from BigQuery (indoor + outdoor values)
        forecast: list of forecast entries from OpenWeatherMap
        motion_detected: whether the PIR motion sensor fired
        last_announcement_time: when the last motion-triggered announcement was made

    Returns:
        list of announcement strings (can be empty if no rules trigger)
    """
    announcements = []
    now = datetime.now()

    indoor_humidity = sensor_data.get("humidity_indoor")
    outdoor_temp = sensor_data.get("temperature_outdoor")
    aqi = sensor_data.get("air_quality")
    wind_speed = sensor_data.get("wind_speed")
    weather_desc = str(sensor_data.get("weather_description", "")).lower()

    # ─────────────────────────────────────────────
    # RULE 1: Motion detected + poor air quality
    # Triggers: motion sensor fires AND AQI > 150
    # Anti-spam: only once per hour maximum
    # ─────────────────────────────────────────────
    if motion_detected and aqi is not None and aqi > 150:
        # Check if we announced in the last 60 minutes
        if last_announcement_time is None or (now - last_announcement_time).seconds > 3600:
            announcements.append(
                f"Heads up coach — outdoor air quality is poor right now with an AQI of {aqi}. "
                f"Consider moving today's cardio session indoors or reducing intensity."
            )

    # ─────────────────────────────────────────────
    # RULE 2: Morning storm warning (runs at 8am)
    # Triggers: current hour is 8am AND rain/storm in forecast
    # ─────────────────────────────────────────────
    if now.hour == 8:
        storm_keywords = ["storm", "thunderstorm", "heavy rain", "heavy shower"]
        storm_entry = None

        for entry in forecast:
            desc = entry.get("description", "").lower()
            if any(keyword in desc for keyword in storm_keywords):
                storm_entry = entry
                break

        if storm_entry:
            storm_time = storm_entry.get("datetime", "later today").split(" ")[1][:5]  # extract HH:MM
            announcements.append(
                f"Good morning coach. Heads up — stormy conditions are expected around {storm_time} today. "
                f"Consider confirming or rescheduling this evening's training session."
            )

    # ─────────────────────────────────────────────
    # RULE 3: 2 hours before training time
    # Triggers: current time is within 5 minutes of 2h before TRAINING_TIME
    # ─────────────────────────────────────────────
    training_dt = get_training_datetime_today()
    minutes_until_training = (training_dt - now).total_seconds() / 60

    if 115 <= minutes_until_training <= 125:  # window of 10 minutes around the 2h mark
        desc_display = str(sensor_data.get("weather_description", "unknown")).title()
        announcements.append(
            f"Training in 2 hours coach. Current pitch conditions: "
            f"{outdoor_temp}°C, {desc_display}, wind at {wind_speed} m/s. "
            f"Plan accordingly and make sure the players are notified."
        )

    # ─────────────────────────────────────────────
    # RULE 4: Dry air in locker room
    # Triggers: indoor humidity below 40%
    # ─────────────────────────────────────────────
    if indoor_humidity is not None and indoor_humidity < 40:
        announcements.append(
            f"Locker room humidity is low at {indoor_humidity}%. "
            f"Remind your players to hydrate well before and during training today."
        )

    # ─────────────────────────────────────────────
    # RULE 5: Frost risk
    # Triggers: outdoor temperature below 2°C
    # ─────────────────────────────────────────────
    if outdoor_temp is not None and outdoor_temp < 2:
        announcements.append(
            f"Frost alert coach — outdoor temperature is {outdoor_temp}°C. "
            f"There is a risk of frost on the pitch. Plan an extended warm-up of at least 15 minutes "
            f"and check the pitch surface before letting players run at full speed."
        )

    # ─────────────────────────────────────────────
    # RULE 6: High heat
    # Triggers: outdoor temperature above 28°C
    # ─────────────────────────────────────────────
    if outdoor_temp is not None and outdoor_temp > 28:
        announcements.append(
            f"High temperature alert — it's {outdoor_temp}°C outside. "
            f"Schedule mandatory hydration breaks every 15 minutes during training "
            f"and avoid peak intensity drills between 12pm and 4pm."
        )

    return announcements


def get_demo_announcement(rule_number: int, sensor_data: dict) -> str:
    """
    Force a specific announcement rule for demo/testing purposes.
    Used during the live defense to demonstrate each rule without waiting for conditions.

    Args:
        rule_number: 1-6 corresponding to each rule
        sensor_data: current sensor data for realistic values

    Returns:
        announcement string
    """
    outdoor_temp = sensor_data.get("temperature_outdoor", 15)
    aqi = sensor_data.get("air_quality", 80)
    indoor_humidity = sensor_data.get("humidity_indoor", 45)
    wind_speed = sensor_data.get("wind_speed", 5)
    weather_desc = str(sensor_data.get("weather_description", "cloudy")).title()
    training_hour = TRAINING_TIME.split(":")[0]

    demos = {
        1: f"Heads up coach — outdoor air quality is poor right now with an AQI of {aqi}. "
           f"Consider moving today's cardio session indoors or reducing intensity.",

        2: f"Good morning coach. Heads up — stormy conditions are expected around {training_hour}:00 today. "
           f"Consider confirming or rescheduling this evening's training session.",

        3: f"Training in 2 hours coach. Current pitch conditions: "
           f"{outdoor_temp}°C, {weather_desc}, wind at {wind_speed} m/s. "
           f"Plan accordingly and make sure the players are notified.",

        4: f"Locker room humidity is low at {indoor_humidity}%. "
           f"Remind your players to hydrate well before and during training today.",

        5: f"Frost alert coach — outdoor temperature is {outdoor_temp}°C. "
           f"There is a risk of frost on the pitch. Plan an extended warm-up of at least 15 minutes.",

        6: f"High temperature alert — it's {outdoor_temp}°C outside. "
           f"Schedule mandatory hydration breaks every 15 minutes during training."
    }

    return demos.get(rule_number, "No announcement for that rule number.")