import os
import struct
import base64
import tempfile
from flask import Flask, request, jsonify, send_file, make_response
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
    data = get_latest_reading()
    if not data:
        return jsonify([])
    return jsonify(check_alerts(data))


@app.route("/averages", methods=["GET"])
def averages():
    days = request.args.get("days", 7, type=int)
    df = get_daily_averages(days)
    return jsonify(df.to_dict(orient="records"))


@app.route("/ask", methods=["POST"])
def ask():
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
    try:
        body = request.get_json()
        audio_b64 = body.get("audio")
        if not audio_b64:
            return jsonify({"error": "No audio received"}), 400
        audio_bytes = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        from voice import process_voice_query
        result = process_voice_query(tmp_path)
        with open(result["audio_path"], "rb") as f:
            audio_response_b64 = base64.b64encode(f.read()).decode("utf-8")
        os.remove(tmp_path)
        os.remove(result["audio_path"])
        return jsonify({
            "question": result["question"],
            "answer": result["answer"],
            "audio": audio_response_b64
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/voice_raw", methods=["POST"])
def voice_raw():
    """
    Reçoit un fichier WAV brut depuis le M5Stack,
    transcrit avec Whisper, répond avec GPT-4o,
    génère audio TTS et renvoie le WAV directement.
    """
    try:
        # Recevoir l'audio brut
        audio_bytes = request.data
        if not audio_bytes:
            return jsonify({"error": "No audio received"}), 400

        # Sauvegarder temporairement
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        # Pipeline complet
        from voice import speech_to_text, answer_weather_question, text_to_speech

        # 1. Transcription
        question = speech_to_text(tmp_path)
        print(f"Question: {question}")
        os.remove(tmp_path)

        # 2. Réponse GPT-4o
        answer = answer_weather_question(question)
        print(f"Answer: {answer}")

        # 3. Text-to-speech → WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            response_path = f.name
        text_to_speech(answer, response_path)

        # 4. Prepend answer text as length-prefixed bytes before WAV data.
        # Format: [4-byte big-endian text length][UTF-8 text][WAV bytes]
        # This is reliably readable by MicroPython urequests (unlike HTTP headers
        # which are not exposed for binary responses in UIFlow builds).
        with open(response_path, "rb") as f:
            wav_bytes = f.read()
        os.remove(response_path)

        text_bytes = answer.encode("utf-8")
        prefix = struct.pack(">I", len(text_bytes))
        body = prefix + text_bytes + wav_bytes

        response = make_response(body)
        response.headers["Content-Type"] = "audio/wav"
        return response

    except Exception as e:
        print(f"voice_raw error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/announce", methods=["POST"])
def announce():
    """
    Accept {"text": "..."} and return TTS audio as WAV.
    Used by the M5Stack for motion-triggered announcements —
    no microphone or STT step, just text → WAV.
    """
    try:
        body = request.get_json()
        if not body or not body.get("text"):
            return jsonify({"error": "No text provided"}), 400
        text = body["text"]

        from voice import text_to_speech
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        text_to_speech(text, tmp_path)

        response = send_file(tmp_path, mimetype="audio/wav", as_attachment=False)

        @response.call_on_close
        def cleanup():
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        return response

    except Exception as e:
        print(f"announce error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)