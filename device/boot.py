"""
boot.py — runs automatically before main.py on every power-on/reset.

Responsibilities:
  1. Load saved WiFi credentials from flash
  2. Connect to WiFi (retry up to WIFI_RETRY_COUNT times)
  3. Sync RTC via NTP on successful connect
  4. Set config.wifi_connected so main.py knows the link status

Kept intentionally lean — no sensor or display imports here so a
sensor failure cannot prevent the network from coming up.
"""
import network
import utime
import config

try:
    import ntptime
    _ntptime_ok = True
except ImportError:
    _ntptime_ok = False


def _connect_wifi():
    creds = config.load_wifi_creds()
    if not creds:
        # No credentials saved yet — wifi_setup.enter() must run first
        return False

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Already connected (e.g. soft-reset without full power cycle)
    if wlan.isconnected():
        config.wifi_connected = True
        return True

    wlan.connect(creds["ssid"], creds["password"])

    for attempt in range(config.WIFI_RETRY_COUNT):
        utime.sleep_ms(2000)
        if wlan.isconnected():
            config.wifi_connected = True
            if _ntptime_ok:
                try:
                    ntptime.settime()
                except Exception:
                    pass  # NTP failure is non-fatal; RTC may be slightly off
            return True

    # All retries exhausted — continue offline; main.py shows banner
    return False


_connect_wifi()
