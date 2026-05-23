import os
import base64
import tempfile
from flask import Flask, request, jsonify
from bigquery_client import (
    insert_sensor_data,
    get_latest_reading,
    get_historical_data,
    get_daily_averages,
    check_alerts
)
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


@app.route("/alerts", methods=["GET"])
def alerts():
    """Return alerts based on the latest sensor reading"""
    data = get_latest_reading()
    if not data:
        return jsonify([])
    return jsonify(check_alerts(data))


@app.route("/averages", methods=["GET"])
def averages():
    """Return daily averages for the last N days (default 7)"""
    days = request.args.get("days", 7, type=int)
    df = get_daily_averages(days)
    return jsonify(df.to_dict(orient="records"))


@app.route("/ask", methods=["POST"])
def ask():
    """Answer a text question about weather/training conditions"""
    question = request.get_json().get("question")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    try:
        from voice import answer_weather_question
        answer = answer_weather_question(question)
        return jsonify({"question": question, "answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/voice", methods=["POST"])
def voice():
    """
    Full voice pipeline: receive audio (base64) -> transcribe -> answer -> return audio (base64)
    Used by the M5Stack for spoken Q&A with the coach assistant.
    Body: {"audio": "<base64 encoded WAV>"}
    """
    try:
        body = request.get_json()
        audio_b64 = body.get("audio")
        if not audio_b64:
            return jsonify({"error": "No audio received"}), 400

        # Decode base64 audio and save to a temp file
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        # Full pipeline: audio -> text -> GPT-4o answer -> audio
        from voice import process_voice_query
        result = process_voice_query(tmp_path)

        # Encode the audio response back to base64 to send over HTTP
        with open(result["audio_path"], "rb") as f:
            audio_response_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Clean up temp files
        os.remove(tmp_path)
        os.remove(result["audio_path"])

        return jsonify({
            "question": result["question"],
            "answer": result["answer"],
            "audio": audio_response_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/announce", methods=["POST"])
def announce():
    """
    Check all 6 announcement rules and return any that trigger.
    Called by the M5Stack when motion is detected or on a schedule.
    Body: {"motion_detected": true/false}
    """
    body = request.get_json() or {}
    motion_detected = body.get("motion_detected", False)

    try:
        from voice import run_announcements
        sensor_data = get_latest_reading()
        forecast_data = get_forecast()
        triggered = run_announcements(sensor_data, forecast_data, motion_detected)
        return jsonify({"triggered": triggered, "count": len(triggered)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/demo-announce", methods=["POST"])
def demo_announce():
    """
    Force a specific announcement rule for live demo/defense purposes.
    Body: {"rule": 1-6}
    """
    body = request.get_json() or {}
    rule_number = body.get("rule", 1)

    try:
        from voice import run_demo_announcement
        sensor_data = get_latest_reading()
        result = run_demo_announcement(rule_number, sensor_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)