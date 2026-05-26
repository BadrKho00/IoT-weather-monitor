from m5stack import *
from m5stack_ui import *
from uiflow import *
from m5stack import touch
import unit
import urequests
import ujson
import time
import gc
import uos
import MicrophonePDM as MIC
import wifiCfg
import network

# --- SENSORS ---
env3_0 = unit.get(unit.ENV3, unit.PORTA)
pir_0  = unit.get(unit.PIR,  unit.PORTB)
tvoc_1 = unit.get(unit.TVOC, (14, 13))

# --- CONFIG ---
FLASK_URL            = "https://iot-weather-middleware-183604469593.europe-west6.run.app"
INTERVAL             = 10
current_page         = 0
total_pages          = 6
last_tts_time        = 0
is_recording         = False
brightness           = 50
volume               = 6
_last_drawn_page     = -1
_mic_initialized     = False
_forecast_in_history = False
_live_blink          = False

# --- PALETTE ---
C_BG     = 0x0A0A0F
C_ACCENT = 0x00E5FF
C_WARM   = 0xFFAB00
C_COOL   = 0x448AFF
C_GREEN  = 0x00E676
C_YELLOW = 0xFFEA00
C_RED    = 0xFF1744
C_DIM    = 0x333344
C_MID    = 0x6666AA
C_WHITE  = 0xDDDDFF
C_PURPLE = 0xBB00FF

# --- LED ---
LED_OFF    = 0x000000
LED_BLUE   = 0x0000FF
LED_CYAN   = 0x00FFFF
LED_GREEN  = 0x00FF00
LED_RED    = 0xFF0000
LED_ORANGE = 0xFF6600
LED_YELLOW = 0xFFFF00
LED_PURPLE = 0x9900FF
LED_WHITE  = 0xFFFFFF
LED_PINK   = 0xFF00AA

# --- FONTS ---
try:
    _FONT_BIG = lcd.FONT_DejaVu40
    _FONT_MED = lcd.FONT_DejaVu24
    _FONT_SM  = lcd.FONT_Default
except AttributeError:
    _FONT_BIG = lcd.FONT_Default
    _FONT_MED = lcd.FONT_Default
    _FONT_SM  = lcd.FONT_Default

def led_set(color, bright=20):
    rgb.setColorAll(color)
    rgb.setBrightness(bright)

def led_page(page):
    colors  = [LED_CYAN, LED_BLUE, LED_GREEN, LED_YELLOW, LED_PURPLE, LED_WHITE]
    brights = [15, 15, 15, 15, 15, 10]
    if 0 <= page < len(colors):
        led_set(colors[page], brights[page])

def vibrate(ms=80):
    try:
        power.setVibrationIntensity(80)
        power.setVibrationEnable(True)
        time.sleep_ms(ms)
        power.setVibrationEnable(False)
    except:
        pass

def vibrate_double():
    try:
        power.setVibrationIntensity(60)
        power.setVibrationEnable(True)
        time.sleep_ms(50)
        power.setVibrationEnable(False)
        time.sleep_ms(60)
        power.setVibrationEnable(True)
        time.sleep_ms(50)
        power.setVibrationEnable(False)
    except:
        pass

# --- SETTINGS STATE ---
settings_menu_active       = False
settings_menu_index        = 0
SETTINGS_MENU_ITEMS        = ["WiFi", "Brightness", "Volume", "Back"]
settings_in_wifi           = False
settings_wifi_networks     = []
settings_wifi_index        = 0
settings_in_keyboard       = False
settings_keyboard_ssid     = ""
settings_keyboard_password = ""
settings_keyboard_index    = 0
KEYBOARD_LIST = list("abcdefghijklmnopqrstuvwxyz0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%&*-_.") + ["<BS>", "<BACK>", "<OK>"]
settings_editing = None

# --- WIFI ---
KNOWN_NETWORKS = [
    ("iot-unil",        ""),
    ("iPhone de Salim", ""),
    ("Maison",          ""),
]
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# --- TOUCH ---
touch_start_x   = None
touch_end_x     = None
last_touch      = False
SWIPE_THRESHOLD = 50

# --- DATA ---
data = {
    "temp_indoor":  "--",
    "humidity":     "--",
    "air_quality":  "--",
    "motion":       False,
    "temp_outdoor": "--",
    "wind":         "--",
    "description":  "--",
    "feels_like":   "--",
    "forecast":     [],
    "alerts":       []
}

# ============================================================
#  GENERAL HELPERS
# ============================================================
def get_time():
    try:
        t = rtc.datetime()
        return "{:02d}:{:02d}".format(t[4], t[5])
    except:
        return "--:--"

def get_date():
    try:
        t = rtc.datetime()
        return "{:02d}/{:02d}/{}".format(t[2], t[1], t[0])
    except:
        return "--/--/----"

def get_battery():
    try:
        return int(power.getBatPercent())
    except:
        return -1

def cleanup_wav():
    for f in ['/flash/question.wav', '/flash/answer.wav', '/flash/announce.wav']:
        try:
            uos.remove(f)
        except:
            pass

def read_sensors():
    try:
        temp = env3_0.temperature
        hum  = env3_0.humidity
    except:
        temp, hum = None, None
    try:
        tvoc = tvoc_1.eCO2
    except:
        tvoc = None
    try:
        motion = pir_0.state
    except:
        motion = False
    return temp, hum, tvoc, motion

# ============================================================
#  DRAW HELPERS
# ============================================================
def _big_value(x, y, val_str, color, unit_str=""):
    lcd.font(_FONT_BIG)
    lcd.print(val_str, x, y, color)
    if unit_str:
        try:
            vw = lcd.textWidth(val_str)
        except:
            vw = len(val_str) * 24
        lcd.font(_FONT_SM)
        lcd.print(unit_str, x + vw + 4, y + 28, color)
    lcd.font(_FONT_SM)

def _med_value(x, y, val_str, color, unit_str=""):
    lcd.font(_FONT_MED)
    lcd.print(val_str, x, y, color)
    if unit_str:
        try:
            vw = lcd.textWidth(val_str)
        except:
            vw = len(val_str) * 14
        lcd.font(_FONT_SM)
        lcd.print(unit_str, x + vw + 3, y + 14, color)
    lcd.font(_FONT_SM)

def _label(x, y, text, color=None):
    if color is None:
        color = C_MID
    lcd.font(_FONT_SM)
    lcd.fillRect(x, y + 2, 4, 4, color)
    lcd.print(text, x + 8, y, color)

def draw_header(title, accent):
    lcd.fillRect(0, 0, 320, 24, 0x0D0D1F)
    lcd.fillRect(0, 23, 320, 2, accent)
    lcd.fillCircle(9, 12, 4, accent)
    lcd.font(_FONT_SM)
    lcd.print(title, 19, 8, accent)
    lcd.print(get_time(), 140, 8, C_WHITE)
    lcd.print(get_date(), 192, 8, C_MID)
    pct = get_battery()
    bat_color = C_GREEN if pct > 60 else (C_YELLOW if pct > 30 else C_RED)
    lcd.print("{}%".format(pct) if pct >= 0 else "--", 276, 8, bat_color)

def draw_card(x, y, w, h, color):
    lcd.fillRoundRect(x, y, w, h, 6, color)

def draw_page_indicator():
    lcd.fillRect(0, 220, 320, 20, C_BG)
    y  = 229
    cx = 160 - (total_pages * 10)
    for i in range(total_pages):
        px = cx + i * 20
        if i == current_page:
            lcd.fillRoundRect(px - 5, y - 4, 16, 8, 4, C_WARM)
        else:
            lcd.fillCircle(px + 3, y, 3, C_DIM)

def _draw_static_bg(page):
    lcd.fillScreen(C_BG)
    lcd.font(_FONT_SM)
    if page == 0:
        draw_header("INDOOR", C_ACCENT)
        draw_card(8,   27, 152, 88, 0x0C1828)
        draw_card(163, 27, 149, 88, 0x0A1628)
        draw_card(8,  119, 152, 68, 0x0C1C0C)
        draw_card(163,119, 149, 68, 0x1C1C08)
    elif page == 1:
        draw_header("OUTDOOR", C_COOL)
        draw_card(8,   27, 304, 84, 0x08081E)
        draw_card(8,  115, 152, 62, 0x0C0C1C)
        draw_card(163,115, 149, 62, 0x081818)
        draw_card(8,  181, 304, 40, 0x0E0E0E)
    elif page == 2:
        draw_header("FORECAST", C_GREEN)
        draw_card(8,  27, 304, 60, 0x091409)
        draw_card(8,  91, 304, 60, 0x091409)
        draw_card(8, 155, 304, 60, 0x091409)
    elif page == 3:
        draw_header("COACH TIP", C_YELLOW)
        draw_card(8, 27, 304, 182, 0x191800)
        lcd.fillRect(18, 88, 284, 1, C_DIM)
    elif page == 4:
        draw_header("ASK ME", C_PURPLE)
        draw_card(8,  27, 304, 102, 0x100010)
        lcd.fillRect(8, 134, 304, 1, C_DIM)
    elif page == 5:
        draw_header("SETTINGS", C_WHITE)

def _draw_data_indoor():
    temp = data["temp_indoor"]
    hum  = data["humidity"]
    aqi  = data["air_quality"]

    lcd.fillRoundRect(9,   28, 150, 86, 5, 0x0C1828)
    lcd.fillRoundRect(164, 28, 147, 86, 5, 0x0A1628)
    lcd.fillRoundRect(9,  120, 150, 66, 5, 0x0C1C0C)
    lcd.fillRoundRect(164,120, 147, 66, 5, 0x1C1C08)

    lcd.fillRect(8,   27, 3, 88, C_WARM)
    lcd.fillRect(163, 27, 3, 88, C_COOL)
    lcd.fillRect(8,  119, 3, 68, C_GREEN)
    lcd.fillRect(163,119, 3, 68, C_YELLOW)

    _label(20, 34, "TEMPERATURE")
    t_str = str(round(temp, 1)) if isinstance(temp, float) else str(temp)
    _big_value(18, 47, t_str, C_WARM, chr(176) + "C")

    hum_color = C_RED if isinstance(hum, float) and hum < 40 else C_COOL
    _label(172, 34, "HUMIDITY")
    h_str = str(round(hum, 1)) if isinstance(hum, float) else str(hum)
    _big_value(172, 47, h_str, hum_color, "%")
    if isinstance(hum, float) and hum < 40:
        lcd.font(_FONT_SM)
        lcd.print("LOW!", 172, 96, C_RED)

    if isinstance(aqi, int):
        aqi_color = C_GREEN if aqi < 100 else (C_YELLOW if aqi < 150 else C_RED)
        aqi_label = "Good" if aqi < 100 else ("Fair" if aqi < 150 else "Poor")
    else:
        aqi_color = C_WHITE
        aqi_label = ""
    _label(18, 126, "AIR QUALITY")
    lcd.font(_FONT_MED)
    lcd.print(str(aqi) if isinstance(aqi, int) else "--", 18, 142, aqi_color)
    lcd.font(_FONT_SM)
    if aqi_label:
        lcd.print(aqi_label, 18, 168, aqi_color)

    motion_text  = "Detected" if data["motion"] else "None"
    motion_color = C_WARM if data["motion"] else C_GREEN
    _label(172, 126, "MOTION")
    ring_c  = C_WARM if data["motion"] else 0x1A3A1A
    inner_c = C_RED  if data["motion"] else C_GREEN
    lcd.fillCircle(185, 152, 12, ring_c)
    lcd.fillCircle(185, 152,  7, inner_c)
    lcd.font(_FONT_SM)
    lcd.print(motion_text, 204, 147, motion_color)

    lcd.fillRect(8, 191, 304, 24, C_BG)
    if data["alerts"]:
        lcd.fillRoundRect(8, 191, 304, 22, 4, 0x2A0000)
        lcd.fillRect(8, 191, 3, 22, C_RED)
        lcd.font(_FONT_SM)
        lcd.print("! " + str(data["alerts"][0])[:30], 16, 198, C_RED)

    # Pulsing LIVE dot — toggled every second by _anim_counter in main loop
    _dot_col = C_GREEN if _live_blink else 0x003300
    lcd.fillRect(268, 205, 48, 12, C_BG)
    lcd.font(_FONT_SM)
    lcd.print("LIVE", 272, 207, _dot_col)
    lcd.fillCircle(308, 212, 4, _dot_col)

def _draw_data_outdoor():
    lcd.fillRoundRect(9,   28,  302, 82, 5, 0x08081E)
    lcd.fillRoundRect(9,  116, 150, 60, 5, 0x0C0C1C)
    lcd.fillRoundRect(164,116, 147, 60, 5, 0x081818)
    lcd.fillRoundRect(9,  182, 302, 38, 5, 0x0E0E0E)

    lcd.fillRect(8,   27, 3, 84, C_COOL)
    lcd.fillRect(8,  115, 3, 62, C_ACCENT)
    lcd.fillRect(163,115, 3, 62, C_GREEN)
    lcd.fillRect(8,  181, 3, 40, C_MID)

    _label(20, 34, "OUTDOOR TEMP")
    t_str = str(round(data["temp_outdoor"], 1)) if isinstance(data["temp_outdoor"], float) else str(data["temp_outdoor"])
    _big_value(20, 47, t_str, C_WARM, chr(176) + "C")

    _label(18, 122, "FEELS LIKE")
    feels = data["feels_like"]
    f_str = str(round(feels, 1)) if isinstance(feels, float) else str(feels)
    _med_value(18, 138, f_str, C_WHITE, chr(176) + "C")

    _label(172, 122, "WIND")
    w_str = str(round(data["wind"], 1)) if isinstance(data["wind"], float) else str(data["wind"])
    _med_value(172, 138, w_str, C_ACCENT, " m/s")

    _label(18, 188, "CONDITIONS")
    lcd.font(_FONT_SM)
    lcd.print(str(data["description"])[:30], 18, 200, C_WHITE)

def _draw_data_forecast():
    items_y = [27, 91, 155]
    for i, y in enumerate(items_y):
        lcd.fillRoundRect(9, y + 1, 302, 58, 5, 0x091409)
        lcd.fillRect(8, y, 3, 60, C_GREEN)
        if i < len(data["forecast"]):
            item  = data["forecast"][i]
            dt    = str(item.get("datetime", ""))[:16]
            temp  = item.get("temperature", "--")
            desc  = str(item.get("description", ""))[:24]
            lcd.font(_FONT_SM)
            lcd.print(dt, 18, y + 8, C_MID)
            t_str   = "{}{}C".format(round(temp) if isinstance(temp, float) else temp, chr(176))
            t_color = C_COOL if (isinstance(temp, float) and temp < 10) else (C_WARM if isinstance(temp, float) and temp > 20 else C_WHITE)
            lcd.font(_FONT_MED)
            lcd.print(t_str, 216, y + 4, t_color)
            lcd.font(_FONT_SM)
            lcd.print(desc, 18, y + 36, C_WHITE)
        else:
            lcd.font(_FONT_SM)
            lcd.print("--", 18, y + 24, C_DIM)
    if not data["forecast"]:
        lcd.font(_FONT_SM)
        lcd.print("No data available", 90, 110, C_MID)
    lcd.fillRect(8, 215, 304, 10, C_BG)
    lcd.font(_FONT_SM)
    lcd.print("B: history charts", 92, 205, C_MID)

def _draw_data_coach():
    lcd.fillRoundRect(9, 28, 302, 180, 5, 0x191800)
    lcd.fillRect(18, 88, 284, 1, C_DIM)
    l1, l2, l3 = get_coach_tip()

    ix, iy = 148, 60
    tip_l = l1.lower()
    if "rain" in tip_l or "storm" in tip_l:
        lcd.fillCircle(ix,     iy - 4, 7, C_COOL)
        lcd.fillCircle(ix + 8, iy - 6, 6, C_COOL)
        lcd.fillRect(ix - 7, iy - 4, 22, 8, C_COOL)
        for dx in [-6, 0, 6]:
            lcd.fillRect(ix + dx, iy + 6, 2, 6, C_ACCENT)
    elif "hot" in tip_l:
        lcd.fillCircle(ix, iy, 9, C_WARM)
        for dx, dy in [(0,-15),(11,-10),(15,0),(11,10),(0,15),(-11,10),(-15,0),(-11,-10)]:
            lcd.fillRect(ix + dx - 1, iy + dy - 1, 3, 3, C_WARM)
    elif "cold" in tip_l or "wind" in tip_l:
        lcd.drawLine(ix - 12, iy, ix + 12, iy, C_ACCENT)
        lcd.drawLine(ix, iy - 12, ix, iy + 12, C_ACCENT)
        lcd.drawLine(ix - 8, iy - 8, ix + 8, iy + 8, C_ACCENT)
        lcd.drawLine(ix + 8, iy - 8, ix - 8, iy + 8, C_ACCENT)
    elif "air" in tip_l or "poor" in tip_l:
        lcd.drawLine(ix, iy - 13, ix - 11, iy + 8, C_RED)
        lcd.drawLine(ix - 11, iy + 8, ix + 11, iy + 8, C_RED)
        lcd.drawLine(ix + 11, iy + 8, ix, iy - 13, C_RED)
        lcd.font(_FONT_SM)
        lcd.print("!", ix - 2, iy - 3, C_RED)
    else:
        lcd.fillCircle(ix, iy, 12, C_GREEN)
        lcd.drawLine(ix - 6, iy + 2, ix - 1, iy + 7, C_BG)
        lcd.drawLine(ix - 1, iy + 7, ix + 8, iy - 5, C_BG)

    lcd.font(_FONT_SM)
    lcd.print(l1[:32], 18, 40, C_YELLOW)
    lcd.print(l2[:36], 18, 100, C_WHITE)
    lcd.print(l3[:36], 18, 128, C_WHITE)
    lcd.fillRect(18, 158, 284, 1, C_DIM)
    lcd.print("Swipe left/right to navigate", 18, 166, C_DIM)

def _draw_motion_only():
    lcd.fillRoundRect(164,120, 147, 66, 5, 0x1C1C08)
    lcd.fillRect(163,119, 3, 68, C_YELLOW)
    motion_text  = "Detected" if data["motion"] else "None"
    motion_color = C_WARM if data["motion"] else C_GREEN
    _label(172, 126, "MOTION")
    ring_c  = C_WARM if data["motion"] else 0x1A3A1A
    inner_c = C_RED  if data["motion"] else C_GREEN
    lcd.fillCircle(185, 152, 12, ring_c)
    lcd.fillCircle(185, 152,  7, inner_c)
    lcd.font(_FONT_SM)
    lcd.print(motion_text, 204, 147, motion_color)

# ============================================================
#  FETCH
# ============================================================
def fetch_latest():
    try:
        r = urequests.get(FLASK_URL + "/latest")
        if r.status_code == 200:
            d = ujson.loads(r.text)
            r.close()
            data["temp_indoor"]  = d.get("temperature_indoor", "--")
            data["humidity"]     = d.get("humidity_indoor", "--")
            data["air_quality"]  = d.get("air_quality", "--")
            data["motion"]       = d.get("motion_detected", False)
            data["temp_outdoor"] = d.get("temperature_outdoor", "--")
            data["wind"]         = d.get("wind_speed", "--")
            data["description"]  = d.get("weather_description", "--")
            temp_out = d.get("temperature_outdoor", None)
            data["feels_like"] = round(temp_out - 2, 1) if isinstance(temp_out, float) else "--"
        else:
            r.close()
    except:
        pass

def fetch_forecast():
    try:
        r = urequests.get(FLASK_URL + "/forecast")
        if r.status_code == 200:
            f = ujson.loads(r.text)
            r.close()
            if isinstance(f, list) and len(f) > 0:
                data["forecast"] = f[::8][:3]
        else:
            r.close()
    except:
        pass

def fetch_alerts():
    try:
        r = urequests.get(FLASK_URL + "/alerts")
        if r.status_code == 200:
            a = ujson.loads(r.text)
            r.close()
            data["alerts"] = a if a else []
        else:
            r.close()
    except:
        pass

def fetch_indoor_history():
    try:
        r = urequests.get(FLASK_URL + "/history?hours=24")
        if r.status_code == 200:
            rows = ujson.loads(r.text)
            r.close()
            return rows if isinstance(rows, list) else []
        r.close()
    except:
        pass
    return []

def send_sensor_data():
    temp, hum, tvoc, motion = read_sensors()
    payload = {
        "temperature_indoor": round(temp, 1) if temp is not None else 0,
        "humidity_indoor":    round(hum,  1) if hum  is not None else 0,
        "air_quality":        int(tvoc)      if tvoc is not None else 0,
        "motion_detected":    bool(motion)
    }
    try:
        r = urequests.post(
            FLASK_URL + "/data",
            headers={"Content-Type": "application/json"},
            data=ujson.dumps(payload)
        )
        if r.status_code == 200:
            r.close()
            data["temp_indoor"] = payload["temperature_indoor"]
            data["humidity"]    = payload["humidity_indoor"]
            data["air_quality"] = payload["air_quality"]
            data["motion"]      = payload["motion_detected"]
        else:
            r.close()
    except:
        pass

# ============================================================
#  COACH TIP
# ============================================================
def get_coach_tip():
    desc     = str(data["description"]).lower()
    temp     = data["temp_outdoor"]
    wind     = data["wind"]
    humidity = data["humidity"]
    aqi      = data["air_quality"]
    try:
        if "rain" in desc or "storm" in desc:
            return "Rain expected!", "Bring waterproof gear", "and warm clothes!"
        elif isinstance(temp, (float, int)) and temp > 25:
            return "Hot day ahead!", "Hydrate every 15min", "during training!"
        elif isinstance(temp, (float, int)) and temp < 5:
            return "Cold weather!", "Warm up thoroughly", "before training!"
        elif isinstance(wind, (float, int)) and wind > 10:
            return "Strong winds!", "Adjust your drills", "accordingly!"
        elif isinstance(humidity, (float, int)) and humidity < 40:
            return "Low humidity!", "Drink more water", "stay hydrated!"
        elif isinstance(aqi, int) and aqi > 150:
            return "Poor air quality!", "Avoid intense", "cardio today!"
        else:
            return "Perfect conditions!", "Great session", "ahead! Go team!"
    except:
        return "Check conditions", "before training", "Stay safe!"

# ============================================================
#  SETTINGS STATE FLUSH
# ============================================================
def _flush_settings_state():
    global settings_menu_active, settings_menu_index
    global settings_in_wifi, settings_wifi_networks, settings_wifi_index
    global settings_in_keyboard, settings_keyboard_ssid, settings_keyboard_password
    global settings_keyboard_index, settings_editing
    settings_menu_active       = False
    settings_menu_index        = 0
    settings_in_wifi           = False
    settings_wifi_networks     = []
    settings_wifi_index        = 0
    settings_in_keyboard       = False
    settings_keyboard_ssid     = ""
    settings_keyboard_password = ""
    settings_keyboard_index    = 0
    settings_editing           = None

# ============================================================
#  SPEECH
# ============================================================
def ask_question():
    global is_recording, _last_drawn_page, _mic_initialized
    is_recording = True
    vibrate()

    def _ask_screen(line1, color1, line2="", color2=None, stripe=C_PURPLE):
        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 27, 304, 102, 0x100010)
        lcd.fillRect(8, 27, 3, 102, stripe)
        lcd.font(_FONT_MED)
        lcd.print(line1, 22, 44, color1)
        if line2:
            lcd.font(_FONT_SM)
            lcd.print(line2, 22, 74, color2 if color2 else C_MID)
        lcd.font(_FONT_SM)

    _ask_screen("Get ready...", C_YELLOW, "Releasing audio bus", C_MID)
    led_set(LED_ORANGE)
    time.sleep(2)

    try:
        # Step 1: Release speaker I2S bus
        try:
            speaker.deinit()
        except Exception:
            pass
        gc.collect()
        time.sleep_ms(1000)
        gc.collect()

        # Step 2: Deinit MIC only if currently live
        if _mic_initialized:
            try:
                MIC.deinit(1000)
            except Exception:
                pass
            _mic_initialized = False
            gc.collect()
            time.sleep_ms(500)

        # Step 3: Double GC
        gc.collect()
        time.sleep_ms(200)
        gc.collect()
        time.sleep_ms(300)

        # Step 4: Begin MIC at 8 kHz (small DMA buffer survives fragmented heap)
        MIC.begin(pin_ws=0, pin_data=34, sample_rate_hz=8000,
                  buffer_length_ms=500, block_length_ms=100)
        _mic_initialized = True

        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 27, 304, 102, 0x200010)
        lcd.fillRect(8, 27, 3, 102, C_RED)
        lcd.fillRoundRect(20, 38, 14, 20, 5, C_RED)
        lcd.fillRect(26, 58, 2, 6, C_RED)
        lcd.drawLine(20, 64, 36, 64, C_RED)
        lcd.font(_FONT_MED)
        lcd.print("Recording...", 46, 38, C_RED)
        lcd.font(_FONT_SM)
        lcd.print("5 seconds  speak now!", 46, 68, C_WHITE)
        lcd.print("Keep device still", 46, 84, C_MID)
        led_set(LED_RED, 25)

        with open('/flash/question.wav', 'wb') as f_mic:
            MIC.recordStart(f_mic, 5000)
            MIC.waitRecordDone(7000)

        # Step 5: Release MIC I2S aggressively
        MIC.deinit(2000)
        _mic_initialized = False
        gc.collect()
        time.sleep_ms(800)
        gc.collect()
        time.sleep_ms(800)
        gc.collect()
        time.sleep_ms(400)

        _ask_screen("Processing...", C_YELLOW, "Sending to AI", C_MID, C_WARM)
        led_set(LED_ORANGE)

        # Step 6: POST via bytearray (urequests needs len(); file objects have no __len__)
        try:
            file_size = uos.stat('/flash/question.wav')[6]
        except Exception:
            file_size = 0

        gc.collect()
        buf = bytearray(file_size)
        with open('/flash/question.wav', 'rb') as f:
            f.readinto(buf)

        r = urequests.post(
            FLASK_URL + "/voice_raw",
            data=buf,
            headers={
                "Content-Type":   "audio/wav",
                "Content-Length": str(file_size)
            }
        )
        del buf
        gc.collect()

        if r.status_code == 200:
            answer_text = ""
            try:
                answer_text = r.headers.get("x-answer", "") or r.headers.get("X-Answer", "")
            except Exception:
                pass

            led_set(LED_CYAN, 20)
            lcd.fillScreen(C_BG)
            draw_header("ASK ME", C_PURPLE)

            if answer_text:
                draw_card(8, 27, 304, 106, 0x0A0018)
                lcd.fillRect(8, 27, 3, 106, C_ACCENT)
                _label(18, 33, "ANSWER", C_ACCENT)
                a = answer_text[:78]
                lcd.font(_FONT_SM)
                lcd.print(a[:26],  18, 50, C_WHITE)
                if len(a) > 26:
                    lcd.print(a[26:52], 18, 66, C_WHITE)
                if len(a) > 52:
                    lcd.print(a[52:78], 18, 82, C_WHITE)
                lcd.print("Playing response...", 18, 100, C_ACCENT)
            else:
                draw_card(8, 27, 304, 68, 0x0A0018)
                lcd.fillRect(8, 27, 3, 68, C_ACCENT)
                lcd.font(_FONT_MED)
                lcd.print("Playing...", 22, 44, C_GREEN)
                lcd.font(_FONT_SM)

            if data["forecast"]:
                fc      = data["forecast"][0]
                fc_temp = fc.get("temperature", "--")
                fc_desc = str(fc.get("description", ""))[:22]
                draw_card(8, 138, 304, 50, 0x091409)
                lcd.fillRect(8, 138, 3, 50, C_GREEN)
                _label(18, 144, "NEXT FORECAST", C_GREEN)
                lcd.font(_FONT_SM)
                lcd.print("{}  {}{}C  {}".format(
                    str(fc.get("datetime", ""))[:10],
                    round(fc_temp) if isinstance(fc_temp, float) else fc_temp,
                    chr(176), fc_desc)[:34], 18, 160, C_WHITE)

            with open('/flash/answer.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            del r
            gc.collect()

            time.sleep_ms(500)
            speaker.playWAV('/flash/answer.wav', volume=volume)

            lcd.font(_FONT_SM)
            lcd.print("Done!  Press B to ask again", 18, 196, C_GREEN)

            try:
                speaker.deinit()
            except Exception:
                pass
            gc.collect()
            time.sleep_ms(1500)
            gc.collect()
            time.sleep_ms(500)

        else:
            r.close()
            lcd.fillScreen(C_BG)
            draw_header("ASK ME", C_PURPLE)
            draw_card(8, 27, 304, 80, 0x200000)
            lcd.fillRect(8, 27, 3, 80, C_RED)
            lcd.font(_FONT_MED)
            lcd.print("Server Error", 22, 44, C_RED)
            lcd.font(_FONT_SM)
            try:
                lcd.print(r.text[:28], 22, 72, C_MID)
            except Exception:
                pass
            led_set(LED_RED)

    except Exception as e:
        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 27, 304, 80, 0x200000)
        lcd.fillRect(8, 27, 3, 80, C_RED)
        lcd.font(_FONT_SM)
        lcd.print("Error:", 22, 40, C_RED)
        lcd.print(str(e)[:30], 22, 56, C_MID)
        led_set(LED_RED)

    finally:
        try:
            speaker.deinit()
        except Exception:
            pass
        if _mic_initialized:
            try:
                MIC.deinit(1000)
            except Exception:
                pass
            _mic_initialized = False
        cleanup_wav()
        gc.collect()
        time.sleep_ms(500)
        gc.collect()
        is_recording     = False
        _last_drawn_page = -1
        time.sleep(3)
        show_current_page()
        led_page(current_page)

# ============================================================
#  PIR
# ============================================================
def play_weather_announcement():
    global last_tts_time
    if is_recording:
        return
    now = time.time()
    if now - last_tts_time < 3600:
        return

    desc = str(data["description"]).lower()
    temp = data["temp_outdoor"]
    wind = data["wind"]
    hum  = data["humidity"]
    aqi  = data["air_quality"]
    try:
        if "rain" in desc or "storm" in desc:
            msg = ("Hello coach! Rain expected today. "
                   "Remember to bring waterproof gear for training!")
        elif isinstance(temp, (int, float)) and temp > 25:
            msg = ("Hello coach! It is {} degrees outside today. "
                   "Make sure players hydrate every fifteen minutes!").format(int(temp))
        elif isinstance(temp, (int, float)) and temp < 5:
            msg = ("Hello coach! It is only {} degrees outside. "
                   "Plan a long progressive warm-up before training!").format(int(temp))
        elif isinstance(wind, (int, float)) and wind > 10:
            msg = ("Hello coach! Strong wind at {} metres per second. "
                   "Adjust your drills accordingly!").format(round(wind, 1))
        elif isinstance(hum, (int, float)) and hum < 40:
            msg = ("Hello coach! Humidity is very low at {} percent. "
                   "Insist on hydration during training!").format(int(hum))
        elif isinstance(aqi, int) and aqi > 150:
            msg = ("Hello coach! Air quality is poor today. "
                   "Avoid intense cardio exercises!")
        else:
            msg = ("Hello coach! Conditions are ideal for training. "
                   "Have a great session with the team!")
    except Exception:
        msg = "Hello coach! Please check conditions before training."

    try:
        led_set(LED_PINK, 25)
        r = urequests.post(
            FLASK_URL + "/announce",
            headers={"Content-Type": "application/json"},
            data=ujson.dumps({"text": msg})
        )
        if r.status_code == 200:
            with open('/flash/announce.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            del r
            gc.collect()
            last_tts_time = now
            speaker.playWAV('/flash/announce.wav', volume=volume)
            try:
                speaker.deinit()
            except Exception:
                pass
            gc.collect()
            try:
                uos.remove('/flash/announce.wav')
            except Exception:
                pass
        else:
            r.close()
    except Exception:
        pass
    led_page(current_page)

# ============================================================
#  FORECAST HISTORY CHART
# ============================================================
def show_page_forecast_history():
    global _last_drawn_page
    lcd.fillScreen(C_BG)
    draw_header("HISTORY", C_GREEN)
    lcd.font(_FONT_SM)
    lcd.print("Loading...", 118, 112, C_MID)

    rows = fetch_indoor_history()

    lcd.fillScreen(C_BG)
    draw_header("HISTORY  (last 24 h)", C_GREEN)

    if not rows:
        draw_card(60, 80, 200, 60, 0x0C1C0C)
        lcd.fillRect(60, 80, 3, 60, C_GREEN)
        lcd.font(_FONT_SM)
        lcd.print("No data available", 74, 104, C_MID)
        lcd.print("A: back", 120, 160, C_DIM)
        draw_page_indicator()
        _last_drawn_page = -1
        return

    temps = []
    hums  = []
    aqis  = []
    for row in rows[-20:]:
        t = row.get("temperature_indoor")
        h = row.get("humidity_indoor")
        a = row.get("air_quality")
        if t is not None: temps.append(float(t))
        if h is not None: hums.append(float(h))
        if a is not None: aqis.append(float(a))

    def _mini_chart(label, values, y_top, bar_color, unit_str):
        draw_card(8, y_top, 304, 52, 0x0A140A)
        lcd.fillRect(8, y_top, 3, 52, bar_color)
        if not values:
            lcd.font(_FONT_SM)
            lcd.print(label + ": no data", 18, y_top + 20, C_MID)
            return
        mn    = min(values)
        mx    = max(values)
        avg   = sum(values) / len(values)
        span  = mx - mn if mx != mn else 1
        ch    = 28
        cy    = y_top + 22
        n     = len(values)
        bar_w = max(1, 280 // n)
        for i, v in enumerate(values):
            h_px = max(1, int((v - mn) / span * ch))
            lcd.fillRect(20 + i * bar_w, cy + ch - h_px, bar_w - 1, h_px, bar_color)
        lcd.font(_FONT_SM)
        lcd.print("{}: avg {:.1f}{}  min {:.1f}  max {:.1f}".format(
            label, avg, unit_str, mn, mx)[:38], 18, y_top + 6, C_WHITE)

    _mini_chart("Temp",     temps, 27,  C_WARM,   "C")
    _mini_chart("Humidity", hums,  83,  C_COOL,   "%")
    _mini_chart("AQI",      aqis,  139, C_YELLOW, "")

    lcd.fillRect(8, 198, 304, 16, C_BG)
    lcd.font(_FONT_SM)
    lcd.print("A: back to forecast", 76, 200, C_DIM)
    draw_page_indicator()
    _last_drawn_page = -1

# ============================================================
#  PAGES
# ============================================================
def show_page_indoor(force_bg=False):
    global _last_drawn_page
    if _last_drawn_page != 0 or force_bg:
        _draw_static_bg(0)
        _last_drawn_page = 0
    _draw_data_indoor()
    draw_page_indicator()

def show_page_outdoor(force_bg=False):
    global _last_drawn_page
    if _last_drawn_page != 1 or force_bg:
        _draw_static_bg(1)
        _last_drawn_page = 1
    _draw_data_outdoor()
    draw_page_indicator()

def show_page_forecast(force_bg=False):
    global _last_drawn_page
    if _forecast_in_history:
        show_page_forecast_history()
        return
    if _last_drawn_page != 2 or force_bg:
        _draw_static_bg(2)
        _last_drawn_page = 2
    _draw_data_forecast()
    draw_page_indicator()

def show_page_coach(force_bg=False):
    global _last_drawn_page
    if _last_drawn_page != 3 or force_bg:
        _draw_static_bg(3)
        _last_drawn_page = 3
    _draw_data_coach()
    draw_page_indicator()

def show_page_ask():
    global _last_drawn_page
    if _last_drawn_page != 4:
        _draw_static_bg(4)
        _last_drawn_page = 4

    lcd.fillRoundRect(9, 28, 302, 100, 5, 0x100010)
    lcd.fillRect(8, 27, 3, 102, C_PURPLE)
    lcd.fillRoundRect(18, 38, 14, 22, 5, C_PURPLE)
    lcd.fillRect(24, 60, 2, 7, C_PURPLE)
    lcd.drawLine(18, 67, 34, 67, C_PURPLE)

    lcd.font(_FONT_MED)
    lcd.print("Press B to ask", 44, 40, C_WHITE)
    lcd.font(_FONT_SM)
    lcd.print("5-second voice question", 44, 68, C_MID)
    lcd.print("Response plays through speaker", 44, 84, C_MID)

    lcd.fillRect(8, 134, 304, 1, C_DIM)
    _label(18, 142, "EXAMPLES", C_MID)
    lcd.font(_FONT_SM)
    draw_card(8, 158, 304, 22, 0x0A0A18)
    lcd.print("Is it good to train outside today?", 18, 164, C_DIM)
    draw_card(8, 184, 304, 22, 0x0A0A18)
    lcd.print("How is the air quality right now?", 18, 190, C_DIM)

    draw_page_indicator()

def show_page_settings():
    global _last_drawn_page
    _last_drawn_page = 5
    lcd.fillScreen(C_BG)
    draw_header("SETTINGS", C_WHITE)

    if settings_in_keyboard:
        draw_card(8, 28, 304, 44, 0x0A0A1E)
        lcd.fillRect(8, 28, 3, 44, C_ACCENT)
        lcd.font(_FONT_SM)
        lcd.print("WiFi: " + settings_keyboard_ssid[:22], 18, 36, C_ACCENT)
        pwd_display = "*" * len(settings_keyboard_password)
        lcd.print("Pass: " + pwd_display[-20:], 18, 52, C_YELLOW)

        lcd.fillRect(8, 78, 304, 1, C_DIM)
        draw_card(80, 88, 68, 30, 0x1C1C00)
        lcd.fillRect(80, 88, 3, 30, C_YELLOW)
        total_k = len(KEYBOARD_LIST)
        prev_i  = (settings_keyboard_index - 1) % total_k
        curr_i  = settings_keyboard_index
        next_i  = (settings_keyboard_index + 1) % total_k
        lcd.print("< " + str(KEYBOARD_LIST[prev_i]), 16, 99, C_MID)
        lcd.font(_FONT_MED)
        lcd.print(str(KEYBOARD_LIST[curr_i]), 94, 92, C_YELLOW)
        lcd.font(_FONT_SM)
        lcd.print(str(KEYBOARD_LIST[next_i]) + " >", 162, 99, C_MID)

        lcd.fillRect(8, 126, 304, 1, C_DIM)
        lcd.print("A: prev   C: next   B: select", 18, 136, C_MID)
        lcd.print("<OK> confirm   <BACK> cancel", 18, 154, C_DIM)
        lcd.print("<BS> deletes last char", 18, 172, C_DIM)

    elif settings_in_wifi:
        _label(18, 32, "AVAILABLE NETWORKS", C_ACCENT)
        lcd.fillRect(8, 48, 304, 1, C_DIM)
        all_items = ["< Back"] + settings_wifi_networks
        if len(all_items) == 1:
            draw_card(60, 80, 200, 50, 0x0A0A1E)
            lcd.font(_FONT_SM)
            lcd.print("Scanning...", 90, 100, C_MID)
        else:
            visible_start = max(0, settings_wifi_index - 1) if settings_wifi_index > 1 else 0
            visible = all_items[visible_start:visible_start + 4]
            for i, ssid in enumerate(visible):
                real_i = visible_start + i
                y = 56 + i * 36
                if real_i == settings_wifi_index:
                    draw_card(8, y - 3, 304, 30, 0x0A1A2E)
                    lcd.fillRect(8, y - 3, 3, 30, C_ACCENT if ssid != "< Back" else C_RED)
                    color = C_RED if ssid == "< Back" else C_ACCENT
                    lcd.font(_FONT_SM)
                    lcd.print("> " + ssid[:28], 16, y + 6, color)
                else:
                    color = 0x884444 if ssid == "< Back" else C_MID
                    lcd.font(_FONT_SM)
                    lcd.print("  " + ssid[:28], 16, y + 6, color)
        lcd.fillRect(8, 202, 304, 1, C_DIM)
        lcd.font(_FONT_SM)
        lcd.print("A/C: navigate   B: select", 18, 210, C_DIM)

    elif settings_menu_active:
        _label(18, 32, "MENU", C_MID)
        lcd.fillRect(8, 48, 304, 1, C_DIM)
        icons = [C_ACCENT, C_COOL, C_WARM, C_RED]
        for i, item in enumerate(SETTINGS_MENU_ITEMS):
            y = 58 + i * 40
            if i == settings_menu_index:
                draw_card(8, y - 4, 304, 34, 0x0A1A2E)
                lcd.fillRect(8, y - 4, 3, 34, icons[i])
                lcd.font(_FONT_SM)
                lcd.print("> " + item, 22, y + 8, icons[i])
            else:
                lcd.fillRect(8, y - 4, 3, 34, C_DIM)
                lcd.font(_FONT_SM)
                lcd.print("  " + item, 22, y + 8, C_MID)
        lcd.fillRect(8, 222, 304, 1, C_DIM)

    elif settings_editing == "brightness":
        draw_card(8, 28, 304, 88, 0x0A0A1E)
        lcd.fillRect(8, 28, 3, 88, C_ACCENT)
        _label(20, 36, "BRIGHTNESS", C_ACCENT)
        lcd.font(_FONT_MED)
        lcd.print("{}%".format(brightness), 20, 54, C_WHITE)
        lcd.font(_FONT_SM)
        lcd.fillRoundRect(20, 82, 264, 8, 4, C_DIM)
        lcd.fillRoundRect(20, 82, max(4, int(264 * brightness / 100)), 8, 4, C_ACCENT)
        lcd.fillRect(8, 124, 304, 1, C_DIM)
        lcd.print("A: decrease  10%    C: increase  10%    B: done", 14, 134, C_MID)

    elif settings_editing == "volume":
        draw_card(8, 28, 304, 88, 0x1A0E00)
        lcd.fillRect(8, 28, 3, 88, C_WARM)
        _label(20, 36, "VOLUME", C_WARM)
        lcd.font(_FONT_MED)
        lcd.print("{}/10".format(volume), 20, 54, C_WHITE)
        lcd.font(_FONT_SM)
        lcd.fillRoundRect(20, 82, 264, 8, 4, C_DIM)
        lcd.fillRoundRect(20, 82, max(4, int(264 * volume / 10)), 8, 4, C_WARM)
        lcd.fillRect(8, 124, 304, 1, C_DIM)
        lcd.print("A: decrease          C: increase          B: done", 14, 134, C_MID)

    else:
        draw_card(8, 28, 304, 52, 0x0A0A1E)
        lcd.fillRect(8, 28, 3, 52, C_ACCENT)
        _label(20, 34, "WIFI", C_ACCENT)
        wifi_status = "Connected: " + wlan.ifconfig()[0] if wlan.isconnected() else "Not connected"
        wifi_color  = C_GREEN if wlan.isconnected() else C_RED
        lcd.font(_FONT_SM)
        lcd.print(wifi_status[:30], 20, 52, wifi_color)

        draw_card(8, 86, 304, 50, 0x0A0A1E)
        lcd.fillRect(8, 86, 3, 50, C_COOL)
        _label(20, 92, "BRIGHTNESS", C_COOL)
        lcd.font(_FONT_SM)
        lcd.print("{}%".format(brightness), 186, 92, C_WHITE)
        lcd.fillRoundRect(20, 108, 264, 6, 3, C_DIM)
        lcd.fillRoundRect(20, 108, max(4, int(264 * brightness / 100)), 6, 3, C_ACCENT)

        draw_card(8, 142, 304, 50, 0x1A0E00)
        lcd.fillRect(8, 142, 3, 50, C_WARM)
        _label(20, 148, "VOLUME", C_WARM)
        lcd.font(_FONT_SM)
        lcd.print("{}/10".format(volume), 186, 148, C_WHITE)
        lcd.fillRoundRect(20, 164, 264, 6, 3, C_DIM)
        lcd.fillRoundRect(20, 164, max(4, int(264 * volume / 10)), 6, 3, C_WARM)

        lcd.fillRect(8, 198, 304, 1, C_DIM)
        lcd.print("B: open menu          A: back to pages", 20, 206, C_MID)

    draw_page_indicator()

def show_current_page():
    if current_page == 0:
        show_page_indoor()
    elif current_page == 1:
        show_page_outdoor()
    elif current_page == 2:
        show_page_forecast()
    elif current_page == 3:
        show_page_coach()
    elif current_page == 4:
        show_page_ask()
    elif current_page == 5:
        show_page_settings()

# ============================================================
#  WIFI CONNECT
# ============================================================
def _do_connect_wifi(ssid, password):
    global _last_drawn_page
    _flush_settings_state()
    _last_drawn_page = -1

    lcd.fillScreen(C_BG)
    draw_header("WIFI", C_ACCENT)
    led_set(LED_ORANGE)
    draw_card(8, 30, 304, 110, 0x08081E)
    lcd.fillRect(8, 30, 3, 110, C_ACCENT)
    _label(18, 38, "CONNECTING TO", C_ACCENT)
    lcd.font(_FONT_SM)
    lcd.print(ssid[:28], 18, 56, C_YELLOW)
    lcd.fillRect(18, 74, 280, 1, C_DIM)
    lcd.print("Please wait...", 18, 84, C_MID)

    try:
        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(1)
        wlan.connect(ssid, password)
        t0 = time.time()
        while not wlan.isconnected() and time.time() - t0 < 15:
            time.sleep(1)
        if wlan.isconnected():
            led_set(LED_GREEN)
            vibrate_double()
            lcd.print("Connected!", 18, 104, C_GREEN)
            lcd.print(wlan.ifconfig()[0], 18, 120, C_MID)
            time.sleep(2)
            try:
                rtc.settime('ntp', host='cn.pool.ntp.org', tzone=3)
            except:
                pass
            fetch_latest()
            fetch_forecast()
            fetch_alerts()
        else:
            led_set(LED_RED)
            vibrate(200)
            lcd.print("Connection failed", 18, 104, C_RED)
            time.sleep(2)
    except Exception as e:
        led_set(LED_RED)
        lcd.print("ERR: {}".format(str(e)[:24]), 18, 104, C_RED)
        time.sleep(2)

    show_page_settings()

# ============================================================
#  NAVIGATION
# ============================================================
def handle_swipe(dx):
    global current_page, _forecast_in_history
    if current_page == 5 and (settings_menu_active or settings_in_wifi
                               or settings_in_keyboard
                               or settings_editing is not None):
        return
    if dx > SWIPE_THRESHOLD:
        vibrate()
        _flush_settings_state()
        _forecast_in_history = False
        current_page = (current_page - 1) % total_pages
        show_current_page()
        led_page(current_page)
    elif dx < -SWIPE_THRESHOLD:
        vibrate()
        _flush_settings_state()
        _forecast_in_history = False
        current_page = (current_page + 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_left_pressed():
    global current_page, settings_menu_index, settings_wifi_index
    global settings_keyboard_index, brightness, volume, _forecast_in_history
    vibrate()
    if current_page == 5:
        if settings_in_keyboard:
            settings_keyboard_index = (settings_keyboard_index - 1) % len(KEYBOARD_LIST)
            show_page_settings()
        elif settings_in_wifi:
            settings_wifi_index = max(0, settings_wifi_index - 1)
            show_page_settings()
        elif settings_menu_active:
            settings_menu_index = (settings_menu_index - 1) % len(SETTINGS_MENU_ITEMS)
            show_page_settings()
        elif settings_editing == "brightness":
            brightness = max(10, brightness - 10)
            screen.set_screen_brightness(brightness)
            show_page_settings()
        elif settings_editing == "volume":
            volume = max(1, volume - 1)
            show_page_settings()
        else:
            _flush_settings_state()
            current_page = 4
            show_current_page()
            led_page(current_page)
    elif current_page == 2 and _forecast_in_history:
        _forecast_in_history = False
        show_page_forecast()
    else:
        _forecast_in_history = False
        current_page = (current_page - 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_right_pressed():
    global current_page, settings_menu_index, settings_wifi_index
    global settings_keyboard_index, brightness, volume, _forecast_in_history
    vibrate()
    if current_page == 5:
        if settings_in_keyboard:
            settings_keyboard_index = (settings_keyboard_index + 1) % len(KEYBOARD_LIST)
            show_page_settings()
        elif settings_in_wifi:
            all_items = ["< Back"] + settings_wifi_networks
            settings_wifi_index = min(len(all_items) - 1, settings_wifi_index + 1)
            show_page_settings()
        elif settings_menu_active:
            settings_menu_index = (settings_menu_index + 1) % len(SETTINGS_MENU_ITEMS)
            show_page_settings()
        elif settings_editing == "brightness":
            brightness = min(100, brightness + 10)
            screen.set_screen_brightness(brightness)
            show_page_settings()
        elif settings_editing == "volume":
            volume = min(10, volume + 1)
            show_page_settings()
        else:
            _flush_settings_state()
            current_page = (current_page + 1) % total_pages
            show_current_page()
            led_page(current_page)
    else:
        _forecast_in_history = False
        current_page = (current_page + 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_middle_pressed():
    global settings_menu_active, settings_menu_index
    global settings_in_wifi, settings_wifi_networks, settings_wifi_index
    global settings_in_keyboard, settings_keyboard_ssid, settings_keyboard_password
    global settings_keyboard_index, settings_editing, current_page, brightness, volume
    global _forecast_in_history
    vibrate()

    if current_page == 5:
        if settings_in_keyboard:
            char = KEYBOARD_LIST[settings_keyboard_index]
            if char == "<BS>":
                settings_keyboard_password = settings_keyboard_password[:-1]
            elif char == "<BACK>":
                settings_in_keyboard       = False
                settings_in_wifi           = True
                settings_keyboard_ssid     = ""
                settings_keyboard_password = ""
                settings_keyboard_index    = 0
                show_page_settings()
                return
            elif char == "<OK>":
                _do_connect_wifi(settings_keyboard_ssid, settings_keyboard_password)
                return
            else:
                settings_keyboard_password += char
            show_page_settings()

        elif settings_in_wifi:
            all_items = ["< Back"] + settings_wifi_networks
            if all_items:
                ssid = all_items[settings_wifi_index]
                if ssid == "< Back":
                    _flush_settings_state()
                    show_page_settings()
                else:
                    found_pass = None
                    for known_ssid, known_pass in KNOWN_NETWORKS:
                        if known_ssid == ssid:
                            found_pass = known_pass
                            break
                    if found_pass is not None:
                        _do_connect_wifi(ssid, found_pass)
                    else:
                        settings_keyboard_ssid     = ssid
                        settings_keyboard_password = ""
                        settings_keyboard_index    = 0
                        settings_in_keyboard       = True
                        settings_in_wifi           = False
                        show_page_settings()

        elif settings_menu_active:
            choice = SETTINGS_MENU_ITEMS[settings_menu_index]
            if choice == "Back":
                _flush_settings_state()
                show_page_settings()
            elif choice == "Brightness":
                _flush_settings_state()
                settings_editing = "brightness"
                show_page_settings()
            elif choice == "Volume":
                _flush_settings_state()
                settings_editing = "volume"
                show_page_settings()
            elif choice == "WiFi":
                _flush_settings_state()
                settings_in_wifi = True
                show_page_settings()
                try:
                    wlan.active(True)
                    time.sleep(1)
                    raw = wlan.scan()
                    if raw:
                        seen  = []
                        clean = []
                        for net in raw:
                            ssid = net[0].decode('utf-8') if isinstance(net[0], bytes) else str(net[0])
                            if ssid and ssid not in seen:
                                seen.append(ssid)
                                clean.append(ssid)
                        settings_wifi_networks = clean
                    else:
                        settings_wifi_networks = []
                except:
                    settings_wifi_networks = []
                show_page_settings()

        elif settings_editing in ("brightness", "volume"):
            _flush_settings_state()
            show_page_settings()

        else:
            settings_menu_active = True
            settings_menu_index  = 0
            show_page_settings()

    elif current_page == 2:
        _forecast_in_history = not _forecast_in_history
        show_page_forecast()

    elif current_page == 4:
        ask_question()

btnA.wasPressed(btn_left_pressed)
btnB.wasPressed(btn_middle_pressed)
btnC.wasPressed(btn_right_pressed)

# ============================================================
#  STARTUP
# ============================================================
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(C_BG)

cleanup_wav()

lcd.fillScreen(C_BG)
lcd.fillRect(0,   0, 320,   3, C_ACCENT)
lcd.fillRect(0, 237, 320,   3, C_ACCENT)
lcd.fillRect(0,   0,   3, 240, C_ACCENT)
lcd.fillRect(317, 0,   3, 240, C_ACCENT)
lcd.fillRect(4,   4, 312,   1, C_DIM)
lcd.fillRect(4, 235, 312,   1, C_DIM)

led_set(LED_BLUE, 15)
vibrate(100)

lcd.fillRect(40, 66, 240, 2, C_DIM)
lcd.font(_FONT_MED)
lcd.print("COACH  WEATHER", 40, 74, C_WARM)
lcd.font(_FONT_SM)
lcd.fillRect(40, 104, 240, 2, C_DIM)
lcd.print("IoT Dashboard  v2.0", 96, 110, C_MID)
lcd.print("M5Stack Core2", 110, 126, C_DIM)

screen.set_screen_brightness(brightness)

BAR_X = 40
BAR_Y = 158
BAR_W = 240
BAR_H = 8
lcd.fillRoundRect(BAR_X, BAR_Y, BAR_W, BAR_H, 4, C_DIM)

def _boot_progress(label, frac):
    lcd.fillRect(BAR_X, BAR_Y + 14, BAR_W, 12, C_BG)
    lcd.font(_FONT_SM)
    lcd.print(label, BAR_X, BAR_Y + 14, C_MID)
    filled = max(6, int(BAR_W * frac))
    lcd.fillRoundRect(BAR_X, BAR_Y, BAR_W, BAR_H, 4, C_DIM)
    lcd.fillRoundRect(BAR_X, BAR_Y, filled, BAR_H, 4, C_ACCENT)
    if filled > 10:
        lcd.fillRect(BAR_X + filled - 4, BAR_Y + 1, 4, BAR_H - 2, C_WHITE)

# WiFi: direct WLAN connect (non-blocking) — avoids UIFlow server handshake
# that hangs in standalone/App mode when wifiCfg.autoConnect is called.
_boot_progress("Connecting to WiFi...", 0.10)
if not wlan.isconnected():
    _cand = []
    try:
        with open('/flash/uiflow/config.json', 'r') as _cf:
            _cfg = ujson.loads(_cf.read())
            _s = _cfg.get('ssid') or _cfg.get('wifi_ssid', '')
            _p = _cfg.get('password') or _cfg.get('wifi_password', '')
            if _s:
                _cand.append((_s, _p))
    except:
        pass
    for _s, _p in KNOWN_NETWORKS:
        if _s:
            _cand.append((_s, _p))
    for _ssid, _pwd in _cand:
        if wlan.isconnected():
            break
        try:
            wlan.connect(_ssid, _pwd)
            _t0 = time.time()
            while not wlan.isconnected() and time.time() - _t0 < 12:
                time.sleep_ms(500)
        except:
            pass

if wlan.isconnected():
    _boot_progress("WiFi  " + wlan.ifconfig()[0], 0.35)
    led_set(LED_CYAN, 10)
else:
    _boot_progress("WiFi unavailable - offline mode", 0.35)
    led_set(LED_ORANGE, 10)

_boot_progress("Syncing time...", 0.50)
try:
    rtc.settime('ntp', host='cn.pool.ntp.org', tzone=3)
    _boot_progress("Time synced", 0.60)
except:
    _boot_progress("Time sync skipped", 0.60)
last_tts_time = time.time() - 3601

_boot_progress("Loading weather data...", 0.72)
fetch_latest()
fetch_forecast()

_boot_progress("Loading alerts...", 0.88)
fetch_alerts()

_boot_progress("Ready!", 1.00)
led_set(LED_GREEN, 15)
vibrate_double()
time.sleep_ms(700)

show_current_page()
led_page(current_page)

touch_start_x  = None
touch_end_x    = None
last_touch     = False
counter        = 0
_fetch_counter = 0
_anim_counter  = 0
_motion_prev   = False

# ============================================================
#  MAIN LOOP
# ============================================================
while True:
    time.sleep_ms(100)

    try:
        if touch.status():
            t = touch.read()
            if t is not None:
                if touch_start_x is None:
                    touch_start_x = t[0]
                touch_end_x = t[0]
                last_touch  = True
        else:
            if last_touch and touch_start_x is not None and touch_end_x is not None:
                dx = touch_end_x - touch_start_x
                handle_swipe(dx)
            touch_start_x = None
            touch_end_x   = None
            last_touch    = False
    except:
        touch_start_x = None
        touch_end_x   = None
        last_touch    = False

    counter       += 1
    _anim_counter += 1

    # 1-second live sensor refresh on indoor page
    if _anim_counter % 10 == 0:
        _live_blink = not _live_blink
        if current_page == 0 and not is_recording:
            _t, _h, _v, _ = read_sensors()
            if _t is not None: data["temp_indoor"] = round(_t, 1)
            if _h is not None: data["humidity"]    = round(_h, 1)
            if _v is not None: data["air_quality"] = int(_v)
            _draw_data_indoor()
            draw_page_indicator()
        if _anim_counter >= 10000:
            _anim_counter = 0

    # Motion: read every 500 ms
    if counter % 5 == 0:
        try:
            motion_now = pir_0.state
            if motion_now != _motion_prev:
                _motion_prev = motion_now
                data["motion"] = bool(motion_now)
                if current_page == 0:
                    _draw_motion_only()
                if motion_now and not is_recording:
                    play_weather_announcement()
        except:
            pass

    # Fetch + send every 30 s
    if counter >= 300:
        counter = 0
        if not wlan.isconnected():
            try:
                wlan.reconnect()
            except:
                pass
        send_sensor_data()
        fetch_latest()
        fetch_alerts()
        if current_page == 0:
            _draw_data_indoor()
            draw_page_indicator()
        elif current_page == 1:
            _draw_data_outdoor()
            draw_page_indicator()
        elif current_page == 2 and not _forecast_in_history:
            _draw_data_forecast()
            draw_page_indicator()
        elif current_page == 3:
            _draw_data_coach()
            draw_page_indicator()

    # Forecast every 5 min
    _fetch_counter += 1
    if _fetch_counter >= 3000:
        _fetch_counter = 0
        fetch_forecast()
