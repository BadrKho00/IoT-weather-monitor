import ujson
import uos

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE_URL = "https://iot-weather-middleware-183604469593.europe-west6.run.app"

# ── Timing (milliseconds unless noted) ───────────────────────────────────────
SENSOR_INTERVAL_MS   = 30_000       # POST /data every 30 seconds
FORECAST_INTERVAL_MS = 1_800_000    # refresh forecast every 30 minutes
PIR_COOLDOWN_S       = 3600         # announce at most once per hour
WIFI_RETRY_COUNT     = 5            # attempts before giving up in boot.py

# ── Flash file names ──────────────────────────────────────────────────────────
WIFI_CREDS_FILE     = "wifi_creds.json"
SGP30_BASELINE_FILE = "sgp30_baseline.json"

# ── Runtime state (mutable, shared across all modules) ────────────────────────
# boot.py sets wifi_connected; api_client reads it before every call.
wifi_connected   = False
last_motion_time = 0         # utime.time() of last PIR announcement
last_sensor_data = {}        # most recent read_all() result
last_api_data    = {}        # most recent GET /latest result
last_forecast    = []        # most recent GET /forecast result
last_alerts      = []        # alerts from most recent POST /data response


# ── Credential helpers ────────────────────────────────────────────────────────

def _exists(path):
    try:
        uos.stat(path)
        return True
    except OSError:
        return False


def load_wifi_creds():
    """Return {"ssid": ..., "password": ...} or None if file missing."""
    if not _exists(WIFI_CREDS_FILE):
        return None
    with open(WIFI_CREDS_FILE, "r") as f:
        return ujson.load(f)


def save_wifi_creds(ssid, password):
    """Persist WiFi credentials to flash."""
    with open(WIFI_CREDS_FILE, "w") as f:
        ujson.dump({"ssid": ssid, "password": password}, f)
