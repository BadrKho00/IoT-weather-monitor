import os
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET = os.getenv("BIGQUERY_DATASET")
TABLE = os.getenv("BIGQUERY_TABLE")
TABLE_ID = f"{PROJECT}.{DATASET}.{TABLE}"

client = bigquery.Client(project=PROJECT)


def insert_sensor_data(data: dict):
    errors = client.insert_rows_json(TABLE_ID, [data])
    if errors:
        print(f"BigQuery insert error: {errors}")
        return False
    return True


def get_latest_reading():
    query = f"""
        SELECT * FROM `{TABLE_ID}`
        ORDER BY timestamp DESC
        LIMIT 1
    """
    result = client.query(query).result()
    rows = list(result)
    return dict(rows[0]) if rows else None


def get_historical_data(hours: int = 24):
    query = f"""
        SELECT * FROM `{TABLE_ID}`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        ORDER BY timestamp ASC
    """
    return client.query(query).to_dataframe()


def get_daily_averages(days: int = 7):
    query = f"""
        SELECT
            DATE(timestamp) as date,
            ROUND(AVG(temperature_indoor), 1) as avg_temp_indoor,
            ROUND(AVG(humidity_indoor), 1) as avg_humidity,
            ROUND(AVG(air_quality), 0) as avg_air_quality
        FROM `{TABLE_ID}`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY date
        ORDER BY date ASC
    """
    return client.query(query).to_dataframe()


def check_alerts(data: dict):
    alerts = []
    if data.get("humidity_indoor", 100) < 40:
        alerts.append("⚠️ Low humidity — below 40%")
    if data.get("air_quality", 0) > 150:
        alerts.append("⚠️ Poor air quality detected")
    return alerts