"""
api_client.py — all HTTP communication with the Flask middleware.

Every function:
  - Returns None immediately if config.wifi_connected is False
  - Catches all network exceptions and returns None (never crashes)
  - Calls response.close() in a finally block to avoid memory leaks
    (urequests does not auto-close connections)

Endpoint reference:
  POST /data       → {"status": "ok", "alerts": [...]}
  GET  /latest     → {temperature_indoor, humidity_indoor, air_quality,
                       motion_detected, temperature_outdoor, humidity_outdoor,
                       weather_description, wind_speed, timestamp}
  GET  /forecast   → [{"datetime": "YYYY-MM-DD HH:MM:SS", "temperature": float,
                        "description": str, "icon": str}, ...]
  POST /voice_raw  → raw WAV bytes (Content-Type: audio/wav)
"""
import urequests
import config


def _get(path):
    if not config.wifi_connected:
        return None
    r = None
    try:
        r = urequests.get(config.MIDDLEWARE_URL + path, timeout=10)
        return r.json()
    except Exception as e:
        print("api_client GET", path, "error:", e)
        return None
    finally:
        if r:
            r.close()


def _post_json(path, body):
    if not config.wifi_connected:
        return None
    r = None
    try:
        r = urequests.post(config.MIDDLEWARE_URL + path, json=body, timeout=15)
        return r.json()
    except Exception as e:
        print("api_client POST", path, "error:", e)
        return None
    finally:
        if r:
            r.close()


def _post_bytes(path, data, content_type):
    if not config.wifi_connected:
        return None
    r = None
    try:
        r = urequests.post(
            config.MIDDLEWARE_URL + path,
            data=data,
            headers={"Content-Type": content_type},
            timeout=20,
        )
        return r.content  # raw bytes
    except Exception as e:
        print("api_client POST bytes", path, "error:", e)
        return None
    finally:
        if r:
            r.close()


# ── Public functions ──────────────────────────────────────────────────────────

def post_data(sensor_dict):
    """
    POST current sensor readings.
    Returns {"status": "ok", "alerts": [...]} or None on failure.
    """
    return _post_json("/data", sensor_dict)


def get_latest():
    """
    GET the most recent enriched row from BigQuery.
    Returns a flat dict with all sensor + weather fields, or None.
    Called once on boot to pre-populate the display before the first read cycle.
    """
    return _get("/latest")


def get_forecast():
    """
    GET the 5-day 3-hour-slot forecast from OpenWeatherMap.
    Returns a list of dicts or [] on failure.
    Each item: {"datetime": str, "temperature": float, "description": str, "icon": str}
    """
    result = _get("/forecast")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("forecast", [])
    return []


def post_voice(wav_bytes):
    """
    POST raw WAV audio to /voice_raw.
    Returns TTS response as raw WAV bytes, or None on failure.
    The middleware runs: Whisper → GPT-4o → TTS → sends back WAV.
    """
    return _post_bytes("/voice_raw", wav_bytes, "audio/wav")
