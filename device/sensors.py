"""
sensors.py — reads all physical sensors on M5Stack Core2.

Wiring (default UIFlow GROVE ports):
  ENV III  (SHT30 + QMP6988) → Port A  (I2C: SDA=32, SCL=33)
  TVOC/eCO2 (SGP30)           → Port A  (shared I2C — different I2C address)
  PIR Motion                  → Port B  (digital GPIO)

Adjust the port constants below if your wiring differs.
"""
import ujson
import uos
import config

# ── Sensor initialisation via UIFlow unit library ─────────────────────────────
# If your UIFlow version uses a different import style, adjust here.
try:
    import unit

    _env3  = unit.get(unit.ENV3, unit.PORTA)   # SHT30 temp+humidity
    _tvoc  = unit.get(unit.TVOC, unit.PORTA)   # SGP30 eCO2 / TVOC
    _pir   = unit.get(unit.PIR,  unit.PORTB)   # PIR digital output
    _hw_ok = True
except Exception as _e:
    print("sensors: hardware init failed —", _e)
    _hw_ok = False


# ── eCO2 → AQI-style index ───────────────────────────────────────────────────
# SGP30 reports eCO2 in ppm (400 = fresh air, 60 000 = extremely poor).
# The middleware stores an integer AQI proxy in the range 0–300.
# Mapping: 400 ppm → 0,  2 200 ppm → 300  (linear, clamped).
def _eco2_to_aqi(eco2_ppm):
    return min(300, max(0, int((eco2_ppm - 400) / 6)))


# ── Public API ────────────────────────────────────────────────────────────────

def read_all():
    """
    Return a dict matching the POST /data payload schema exactly:
      {"temperature_indoor": float, "humidity_indoor": float,
       "air_quality": int, "motion_detected": bool}
    Falls back to last cached values (or zeros) on sensor failure.
    """
    if not _hw_ok:
        return config.last_sensor_data or _zeros()

    try:
        data = {
            "temperature_indoor": round(float(_env3.temperature), 1),
            "humidity_indoor":    round(float(_env3.humidity), 1),
            "air_quality":        _eco2_to_aqi(int(_tvoc.eCO2)),
            "motion_detected":    bool(_pir.state),
        }
        config.last_sensor_data = data
        return data
    except Exception as e:
        print("sensors: read_all error —", e)
        return config.last_sensor_data or _zeros()


def read_pir():
    """Fast PIR-only read for the 1-second polling loop."""
    if not _hw_ok:
        return False
    try:
        return bool(_pir.state)
    except Exception:
        return False


# ── SGP30 baseline persistence ───────────────────────────────────────────────
# The SGP30 takes 12+ hours to self-calibrate from scratch.
# Saving/restoring the baseline dramatically speeds up warmup after reboots.

def load_sgp30_baseline():
    """Restore previously saved SGP30 calibration baseline from flash."""
    if not _hw_ok:
        return
    try:
        uos.stat(config.SGP30_BASELINE_FILE)
        with open(config.SGP30_BASELINE_FILE, "r") as f:
            b = ujson.load(f)
        _tvoc.set_baseline(b["eco2"], b["tvoc"])
    except Exception:
        pass  # No saved baseline yet; sensor will calibrate over time


def save_sgp30_baseline():
    """Persist SGP30 baseline to flash so it survives reboots."""
    if not _hw_ok:
        return
    try:
        eco2_base, tvoc_base = _tvoc.get_baseline()
        with open(config.SGP30_BASELINE_FILE, "w") as f:
            ujson.dump({"eco2": eco2_base, "tvoc": tvoc_base}, f)
    except Exception as e:
        print("sensors: save_sgp30_baseline error —", e)


# ── Internal ──────────────────────────────────────────────────────────────────

def _zeros():
    return {"temperature_indoor": 0.0, "humidity_indoor": 0.0,
            "air_quality": 0, "motion_detected": False}
