import os
from flask import Flask, request, jsonify
from bigquery_client import insert_sensor_data, get_latest_reading, get_historical_data, get_daily_averages, check_alerts
from weather import get_current_weather, get_forecast
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.route("/data", methods=["POST"])
def receive_data():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    data["timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        weather = get_current_weather()
        data.update(weather)
    except Exception as e:
        print(f"Weather fetch failed: {e}")

    alerts = check_alerts(data)
    if alerts:
        print(f"ALERTS: {alerts}")

    success = insert_sensor_data(data)
    if not success:
        return jsonify({"error": "Failed to insert data"}), 500

    return jsonify({"status": "ok", "alerts": alerts}), 200


@app.route("/latest", methods=["GET"])
def latest():
    data = get_latest_reading()
    if not data:
        return jsonify({"error": "No data found"}), 404
    return jsonify(data)


@app.route("/history", methods=["GET"])
def history():
    hours = request.args.get("hours", 24, type=int)
    df = get_historical_data(hours)
    return jsonify(df.to_dict(orient="records"))


@app.route("/forecast", methods=["GET"])
def forecast():
    try:
        data = get_forecast()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)