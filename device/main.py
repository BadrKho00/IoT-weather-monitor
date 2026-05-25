"""
main.py — M5Stack Core2 main application loop.

Runs after boot.py has set config.wifi_connected.

Views (Button A cycles through):
  VIEW_MAIN     — indoor sensors + outdoor weather + current time
  VIEW_FORECAST — 3-hour forecast slots (Button B pages through)

Button mapping:
  A         — cycle VIEW_MAIN ↔ VIEW_FORECAST
  B         — voice Q&A (5-second recording → /voice_raw → play response)
              OR next forecast page (when in VIEW_FORECAST)
  C hold 3s — open WiFi setup (AP mode, evaluator changes credentials here)

PIR trigger:
  When motion is detected and > 1 hour since last announcement,
  display current conditions on screen (voice announcement shown as text).

Non-blocking timing:
  All periodic tasks use utime.ticks_diff() instead of utime.sleep()
  so button polling and PIR checks are never blocked.
"""
import utime
from machine import RTC

import config
import sensors
import api_client
import display
import voice
import wifi_setup

# UIFlow button/touch support
try:
    from m5stack_ui import *
    _m5_ok = True
except ImportError:
    try:
        from m5stack import *
        _m5_ok = True
    except ImportError:
        _m5_ok = False

# ── View state ────────────────────────────────────────────────────────────────
VIEW_MAIN     = 0
VIEW_FORECAST = 1
_view          = VIEW_MAIN
_forecast_page = 0

# ── Periodic task timestamps ──────────────────────────────────────────────────
# Initialise to "already overdue" so each task fires immediately on first loop.
_t_sensor    = -config.SENSOR_INTERVAL_MS
_t_forecast  = -config.FORECAST_INTERVAL_MS
_t_pir       = 0      # PIR check: every 1 000 ms

# Button C hold detection
_btnc_down_at = 0     # ticks_ms when C first detected as pressed; 0 = not held


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_str():
    """Format current RTC time as  "Mon 14:32"."""
    try:
        t = RTC().datetime()          # (year, month, day, weekday, hour, min, sec, sub)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return "{} {:02d}:{:02d}".format(days[t[3] % 7], t[4], t[5])
    except Exception:
        return "--:--"


def _refresh():
    """Redraw whichever view is currently active."""
    if _view == VIEW_MAIN:
        display.show_main(config.last_sensor_data, config.last_api_data, _now_str())
    else:
        display.show_forecast(config.last_forecast, _forecast_page)


def _reconnect():
    """Try to reconnect WiFi; updates config.wifi_connected."""
    import network, ntptime
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        config.wifi_connected = True
        return
    creds = config.load_wifi_creds()
    if not creds:
        config.wifi_connected = False
        return
    wlan.connect(creds["ssid"], creds["password"])
    for _ in range(3):
        utime.sleep_ms(2000)
        if wlan.isconnected():
            config.wifi_connected = True
            try:
                ntptime.settime()
            except Exception:
                pass
            return
    config.wifi_connected = False


# ── Periodic task handlers ────────────────────────────────────────────────────

def _do_sensor_cycle():
    """Read sensors, POST to /data, cache alerts, refresh display."""
    global _t_sensor
    data   = sensors.read_all()
    result = api_client.post_data(data)

    if result is None:
        _reconnect()
    else:
        config.last_alerts = result.get("alerts", [])
        if config.last_alerts:
            display.show_alert(config.last_alerts[0])
            utime.sleep_ms(3000)

    _t_sensor = utime.ticks_ms()
    _refresh()


def _do_forecast_refresh():
    """Fetch and cache the 5-day 3-hour forecast."""
    global _t_forecast
    slots = api_client.get_forecast()
    if slots is not None:
        config.last_forecast = slots
    _t_forecast = utime.ticks_ms()


def _do_voice():
    """5-second recording → /voice_raw → audio playback."""
    display.show_status("Recording... speak now", display.ACCENT)
    wav = voice.record_wav(duration_ms=5000)
    if wav is None:
        display.show_status("Microphone error", display.RED)
        utime.sleep_ms(2000)
        return
    display.show_status("Sending to AI...", display.GREY)
    response_wav = api_client.post_voice(wav)
    if response_wav:
        display.show_status("Playing response", display.GREEN)
        voice.play_wav(response_wav)
    else:
        display.show_status("Voice API unavailable", display.AMBER)
        utime.sleep_ms(2000)


def _do_pir_announce():
    """Show an on-screen announcement when PIR fires (text, not audio)."""
    sd = config.last_sensor_data
    ad = config.last_api_data
    t_in  = sd.get("temperature_indoor",  "--")
    h_in  = sd.get("humidity_indoor",     "--")
    t_out = ad.get("temperature_outdoor", "--")

    msg = "Indoor: {:.0f}{}C  {:.0f}% RH\nOutdoor: {:.0f}{}C".format(
        t_in  if isinstance(t_in,  (int, float)) else 0, chr(176),
        h_in  if isinstance(h_in,  (int, float)) else 0,
        t_out if isinstance(t_out, (int, float)) else 0, chr(176),
    )
    display.show_alert("Motion detected!\n" + msg)
    utime.sleep_ms(3000)


# ── Boot sequence ─────────────────────────────────────────────────────────────

sensors.load_sgp30_baseline()

if not config.wifi_connected:
    display.show_boot_screen()
    display.show_status("No WiFi — hold C for setup", display.AMBER)
    utime.sleep_ms(2000)
else:
    display.show_boot_screen()
    display.show_status("Syncing from cloud...", display.ACCENT)
    latest = api_client.get_latest()
    if latest:
        config.last_api_data = latest
        # Pre-populate indoor readings from last stored BigQuery row
        config.last_sensor_data = {
            "temperature_indoor": latest.get("temperature_indoor", 0.0),
            "humidity_indoor":    latest.get("humidity_indoor",    0.0),
            "air_quality":        latest.get("air_quality",        0),
            "motion_detected":    latest.get("motion_detected",    False),
        }
    slots = api_client.get_forecast()
    if slots:
        config.last_forecast = slots

_refresh()

# ── Main event loop ───────────────────────────────────────────────────────────

while True:
    now = utime.ticks_ms()

    # UIFlow button state must be refreshed each iteration
    if _m5_ok:
        M5.update()

    # ── 30-second sensor cycle ────────────────────────────────────────────────
    if utime.ticks_diff(now, _t_sensor) >= config.SENSOR_INTERVAL_MS:
        _do_sensor_cycle()

    # ── 30-minute forecast refresh ────────────────────────────────────────────
    if utime.ticks_diff(now, _t_forecast) >= config.FORECAST_INTERVAL_MS:
        _do_forecast_refresh()
        if _view == VIEW_FORECAST:
            _refresh()

    # ── PIR poll (every 1 s) ──────────────────────────────────────────────────
    if utime.ticks_diff(now, _t_pir) >= 1000:
        _t_pir = now
        if sensors.read_pir():
            now_s = utime.time()
            if now_s - config.last_motion_time >= config.PIR_COOLDOWN_S:
                config.last_motion_time = now_s
                _do_pir_announce()
                _refresh()

    # ── Offline indicator ─────────────────────────────────────────────────────
    if not config.wifi_connected:
        display.show_status("OFFLINE — hold C for WiFi setup", display.RED)

    # ── Button A: cycle view ──────────────────────────────────────────────────
    if _m5_ok and btnA.wasPressed():
        _view = VIEW_FORECAST if _view == VIEW_MAIN else VIEW_MAIN
        _forecast_page = 0
        _refresh()

    # ── Button B: voice (main view) or next forecast page (forecast view) ─────
    if _m5_ok and btnB.wasPressed():
        if _view == VIEW_FORECAST:
            total_pages = (max(1, len(config.last_forecast)) + 2) // 3
            _forecast_page = (_forecast_page + 1) % total_pages
            _refresh()
        else:
            _do_voice()
            _refresh()

    # ── Button C: hold 3 s = WiFi setup; single press = back to main ─────────
    if _m5_ok:
        if btnC.isPressed():
            if _btnc_down_at == 0:
                _btnc_down_at = now
            elif utime.ticks_diff(now, _btnc_down_at) >= 3000:
                # Hold threshold reached — launch WiFi setup
                _btnc_down_at = 0
                wifi_setup.enter()     # blocks until saved or timeout
                _reconnect()
                _refresh()
        else:
            if _btnc_down_at > 0:
                # Released before 3 s — single press
                held_ms = utime.ticks_diff(now, _btnc_down_at)
                if held_ms < 3000 and _view == VIEW_FORECAST:
                    _view = VIEW_MAIN
                    _refresh()
            _btnc_down_at = 0

    # Short sleep prevents the ESP32 watchdog from triggering on tight loops
    utime.sleep_ms(50)
