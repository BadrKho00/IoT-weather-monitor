"""
display.py — screen rendering for M5Stack Core2 (320 × 240 TFT).

All functions receive data as arguments; they never call the API themselves.
Only this file and main.py should import UIFlow / M5Stack display libraries
to avoid circular import issues in the UIFlow runtime.

Button legend (drawn at the bottom of every screen):
  A — cycle views (main ↔ forecast)
  B — voice Q&A
  C — WiFi setup (hold 3 s)
"""

# UIFlow 2.0 uses m5stack_ui; UIFlow 1.x uses m5stack.
# Both export `lcd` globally after the import.
try:
    from m5stack_ui import *
except ImportError:
    from m5stack import *

# ── Colour palette ────────────────────────────────────────────────────────────
BG     = 0x0D1117   # dark navy
HEADER = 0x161B22   # slightly lighter bar
ACCENT = 0x58A6FF   # blue
GREEN  = 0x3FB950
AMBER  = 0xD29922
RED    = 0xF85149
WHITE  = 0xFFFFFF
GREY   = 0x8B949E

# Screen dimensions
W, H = 320, 240


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clear():
    lcd.clear(BG)


def _header(text):
    lcd.rect(0, 0, W, 28, HEADER, HEADER)
    lcd.font(lcd.FONT_DejaVu18)
    lcd.text(lcd.CENTER, 5, text, WHITE)


def _btn_bar(left="[A]", mid="[B]", right="[C]"):
    lcd.rect(0, 218, W, 22, HEADER, HEADER)
    lcd.font(lcd.FONT_Default)
    lcd.text(6,   222, left,  GREY)
    lcd.text(118, 222, mid,   GREY)
    lcd.text(234, 222, right, GREY)


def _aqi_color(aqi):
    if aqi < 50:
        return GREEN
    if aqi < 150:
        return AMBER
    return RED


def _temp_color(temp):
    if temp < 5 or temp > 30:
        return RED
    if temp < 10 or temp > 26:
        return AMBER
    return GREEN


# ── Public screens ────────────────────────────────────────────────────────────

def show_main(sensor_data, api_data, time_str):
    """
    Main dashboard: indoor sensors (left) + outdoor weather (right) + time.

    sensor_data keys: temperature_indoor, humidity_indoor, air_quality, motion_detected
    api_data keys:    temperature_outdoor, humidity_outdoor, weather_description,
                      wind_speed  (from GET /latest)
    """
    _clear()
    _header(time_str or "--:--")

    sd = sensor_data or {}
    ad = api_data    or {}

    temp_in = sd.get("temperature_indoor", 0.0)
    hum_in  = sd.get("humidity_indoor",    0.0)
    aqi     = sd.get("air_quality",        0)

    # ── Indoor column (left half) ─────────────────────────────────────────────
    lcd.font(lcd.FONT_Default)
    lcd.text(8, 34, "INDOOR", GREY)

    lcd.font(lcd.FONT_DejaVu40)
    lcd.text(8, 50, "{:.0f}{}C".format(temp_in, chr(176)), _temp_color(temp_in))

    lcd.font(lcd.FONT_DejaVu18)
    lcd.text(8, 102, "{:.0f}% RH".format(hum_in),
             AMBER if hum_in < 40 else WHITE)

    lcd.font(lcd.FONT_Default)
    aqi_label = "GOOD" if aqi < 50 else ("MODERATE" if aqi < 150 else "POOR")
    lcd.text(8, 130, "AQI: {}  {}".format(aqi, aqi_label), _aqi_color(aqi))

    motion_txt = "Motion: YES" if sd.get("motion_detected") else "Motion: --"
    lcd.text(8, 146, motion_txt, GREY)

    # ── Vertical divider ──────────────────────────────────────────────────────
    lcd.line(158, 32, 158, 200, GREY)

    # ── Outdoor column (right half) ───────────────────────────────────────────
    lcd.font(lcd.FONT_Default)
    lcd.text(166, 34, "OUTDOOR", GREY)

    temp_out = ad.get("temperature_outdoor")
    wind     = ad.get("wind_speed")
    weather  = ad.get("weather_description", "")

    lcd.font(lcd.FONT_DejaVu40)
    if temp_out is not None:
        lcd.text(166, 50, "{:.0f}{}C".format(temp_out, chr(176)), _temp_color(temp_out))
    else:
        lcd.text(166, 58, "--{}C".format(chr(176)), GREY)

    lcd.font(lcd.FONT_Default)
    if weather:
        lcd.text(166, 102, weather[:16], WHITE)
    if wind is not None:
        lcd.text(166, 118, "{:.1f} m/s".format(wind), GREY)

    hum_out = ad.get("humidity_outdoor")
    if hum_out is not None:
        lcd.text(166, 134, "Hum: {:.0f}%".format(hum_out), GREY)

    # ── Alert strip ───────────────────────────────────────────────────────────
    import config as _cfg
    alerts = _cfg.last_alerts
    if alerts:
        lcd.rect(0, 162, W, 20, 0x3D0D0D, 0x3D0D0D)
        lcd.font(lcd.FONT_Default)
        lcd.text(4, 165, str(alerts[0])[:42], RED)

    _btn_bar("[A] Forecast", "[B] Voice", "[C] WiFi")


def show_forecast(forecast_list, page=0):
    """
    Show 3 forecast slots per page (3-hour resolution from OpenWeatherMap).
    Displays datetime, temperature, and weather description.
    page=0 shows slots 0-2, page=1 shows slots 3-5, etc.
    """
    _clear()
    _header("5-DAY FORECAST")

    slots = forecast_list[page * 3: page * 3 + 3] if forecast_list else []
    col_w = W // 3

    for i, slot in enumerate(slots):
        x = i * col_w + 4

        # datetime e.g. "2024-01-15 12:00:00" → show "Jan 15 12:00"
        dt_str = str(slot.get("datetime", ""))
        if len(dt_str) >= 16:
            label = dt_str[5:10] + " " + dt_str[11:16]  # MM-DD HH:MM
        else:
            label = dt_str[:10]
        lcd.font(lcd.FONT_Default)
        lcd.text(x, 36, label, GREY)

        temp = slot.get("temperature")
        lcd.font(lcd.FONT_DejaVu18)
        if temp is not None:
            lcd.text(x, 58, "{:.0f}{}C".format(temp, chr(176)), _temp_color(temp))
        else:
            lcd.text(x, 58, "--", GREY)

        desc = str(slot.get("description", ""))[:10]
        lcd.font(lcd.FONT_Default)
        lcd.text(x, 88, desc, WHITE)

        # Training suitability based on temperature + description heuristic
        if temp is not None:
            rain_kw = ("rain", "storm", "snow", "drizzle", "thunder")
            is_rain = any(kw in desc.lower() for kw in rain_kw)
            if is_rain or temp < 2 or temp > 30:
                lcd.text(x, 106, "Avoid", RED)
            elif temp < 8 or temp > 26:
                lcd.text(x, 106, "Caution", AMBER)
            else:
                lcd.text(x, 106, "Train OK", GREEN)

        if i < 2:
            lcd.line(col_w * (i + 1), 32, col_w * (i + 1), 200, GREY)

    pages = (max(1, len(forecast_list)) + 2) // 3
    _btn_bar("[A] Back", "p{}/{}".format(page + 1, pages), "[B] Next")


def show_alert(message):
    """Full-screen red alert banner — shown for ~3 seconds then main view resumes."""
    lcd.clear(0x2D0000)
    lcd.font(lcd.FONT_DejaVu24)
    lcd.text(lcd.CENTER, 60, "! ALERT !", RED)
    lcd.font(lcd.FONT_DejaVu18)
    # Simple word-wrap at ~22 chars
    words = str(message).split()
    line, y = "", 110
    for w in words:
        if len(line) + len(w) + 1 > 22:
            lcd.text(lcd.CENTER, y, line.strip(), WHITE)
            line, y = w + " ", y + 26
        else:
            line += w + " "
    if line.strip():
        lcd.text(lcd.CENTER, y, line.strip(), WHITE)


def show_wifi_setup():
    """Instructions screen for AP-mode WiFi setup (see wifi_setup.py)."""
    _clear()
    _header("WiFi Setup")
    lcd.font(lcd.FONT_DejaVu18)
    lcd.text(lcd.CENTER, 46, "AP mode active", WHITE)
    lcd.font(lcd.FONT_Default)
    lcd.text(lcd.CENTER, 80,  "1. Join WiFi network:", GREY)
    lcd.text(lcd.CENTER, 96,  "   M5Stack-Setup", ACCENT)
    lcd.text(lcd.CENTER, 120, "2. Open browser:", GREY)
    lcd.text(lcd.CENTER, 136, "   192.168.4.1", ACCENT)
    lcd.text(lcd.CENTER, 160, "3. Enter SSID + password", GREY)
    lcd.text(lcd.CENTER, 180, "4. Device reboots", GREY)
    _btn_bar("", "", "[C] Cancel")


def show_status(message, color=None):
    """Overlay a small status line at the very bottom (row 205)."""
    c = color if color is not None else GREY
    lcd.rect(0, 204, W, 13, BG, BG)
    lcd.font(lcd.FONT_Default)
    lcd.text(4, 205, str(message)[:44], c)


def show_boot_screen():
    """Splash shown during boot while WiFi is connecting."""
    _clear()
    lcd.font(lcd.FONT_DejaVu24)
    lcd.text(lcd.CENTER, 80, "Weather Monitor", ACCENT)
    lcd.font(lcd.FONT_Default)
    lcd.text(lcd.CENTER, 120, "Connecting to WiFi...", GREY)
