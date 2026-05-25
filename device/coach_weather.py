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

# --- CAPTEURS ---
env3_0 = unit.get(unit.ENV3, unit.PORTA)
pir_0  = unit.get(unit.PIR,  unit.PORTB)
tvoc_1 = unit.get(unit.TVOC, (14, 13))

# --- CONFIG ---
FLASK_URL        = "https://iot-weather-middleware-183604469593.europe-west6.run.app"
INTERVAL         = 10
current_page     = 0
total_pages      = 6
last_tts_time    = 0
is_recording     = False
brightness       = 50
_last_drawn_page = -1
_mic_initialized = False   # True only between MIC.begin() and MIC.deinit()

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
SETTINGS_MENU_ITEMS        = ["WiFi", "Luminosite", "Back"]
settings_in_wifi           = False
settings_wifi_networks     = []
settings_wifi_index        = 0
settings_in_keyboard       = False
settings_keyboard_ssid     = ""
settings_keyboard_password = ""
settings_keyboard_index    = 0
KEYBOARD_LIST = list("abcdefghijklmnopqrstuvwxyz0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%&*-_.") + ["<BS>", "<OK>"]
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
#  HELPERS GENERAUX
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
    for f in ['/flash/question.wav', '/flash/answer.wav']:
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
def draw_header(title, accent):
    lcd.fillRect(0, 0, 320, 22, 0x111122)
    lcd.fillRect(0, 22, 320, 2, accent)
    lcd.print(title,      8,   5, accent)
    lcd.print(get_time(), 118, 5, C_WHITE)
    lcd.print(get_date(), 182, 6, C_MID)
    pct = get_battery()
    bat_color = C_GREEN if pct > 60 else (C_YELLOW if pct > 30 else C_RED)
    lcd.print("{}%".format(pct) if pct >= 0 else "--", 272, 6, bat_color)

def draw_card(x, y, w, h, color):
    lcd.fillRoundRect(x, y, w, h, 6, color)

def draw_page_indicator():
    y = 228
    start_x = 160 - (total_pages * 10)
    for i in range(total_pages):
        x = start_x + i * 20
        if i == current_page:
            lcd.fillCircle(x, y, 5, C_WARM)
        else:
            lcd.fillCircle(x, y, 3, C_DIM)

def _draw_static_bg(page):
    lcd.fillScreen(C_BG)
    if page == 0:
        draw_header("INDOOR", C_ACCENT)
        draw_card(8,   28, 148, 76, 0x0D1A2A)
        draw_card(162, 28, 150, 76, 0x0A1A2A)
        draw_card(8,  110, 148, 60, 0x0D1A0D)
        draw_card(162,110, 150, 60, 0x1A1A0A)
    elif page == 1:
        draw_header("OUTDOOR", C_COOL)
        draw_card(8,   28, 304, 66, 0x0A0A1A)
        draw_card(8,   98, 148, 55, 0x0D0D1A)
        draw_card(162, 98, 150, 55, 0x0A1A1A)
        draw_card(8,  158, 304, 48, 0x0D0D0D)
    elif page == 2:
        draw_header("FORECAST", C_GREEN)
        draw_card(8,  28, 304, 56, 0x0A140A)
        draw_card(8,  88, 304, 56, 0x0A140A)
        draw_card(8, 148, 304, 56, 0x0A140A)
    elif page == 3:
        draw_header("COACH TIP", C_YELLOW)
        draw_card(8, 28, 304, 170, 0x1A1A00)
        lcd.fillRect(20, 90, 280, 1, C_DIM)
    elif page == 4:
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 28, 304, 88, 0x0F000F)
        lcd.fillRect(8, 122, 304, 1, C_DIM)
    elif page == 5:
        draw_header("SETTINGS", C_WHITE)

def _draw_data_indoor():
    temp = data["temp_indoor"]
    hum  = data["humidity"]
    aqi  = data["air_quality"]

    lcd.fillRoundRect(9,   29, 146, 74, 5, 0x0D1A2A)
    lcd.fillRoundRect(163, 29, 148, 74, 5, 0x0A1A2A)
    lcd.fillRoundRect(9,  111, 146, 58, 5, 0x0D1A0D)
    lcd.fillRoundRect(163,111, 148, 58, 5, 0x1A1A0A)

    lcd.print("TEMPERATURE", 18, 34, C_MID)
    lcd.print("{}".format(temp), 18, 50, C_WARM)
    lcd.print("C", 105, 62, C_WARM)

    hum_color = C_RED if isinstance(hum, float) and hum < 40 else C_COOL
    lcd.print("HUMIDITE", 172, 34, C_MID)
    lcd.print("{}%".format(hum), 172, 50, hum_color)
    if isinstance(hum, float) and hum < 40:
        lcd.print("! ALERTE", 172, 88, C_RED)

    if isinstance(aqi, int):
        aqi_color = C_GREEN if aqi < 100 else (C_YELLOW if aqi < 150 else C_RED)
        aqi_text  = "Bon" if aqi < 100 else ("Moyen" if aqi < 150 else "Mauvais")
    else:
        aqi_color = C_WHITE
        aqi_text  = "--"
    lcd.print("AIR QUALITY", 18, 116, C_MID)
    lcd.print(aqi_text, 18, 132, aqi_color)

    motion_text  = "Detecte" if data["motion"] else "Aucun"
    motion_color = C_WARM if data["motion"] else C_GREEN
    lcd.print("MOUVEMENT", 172, 116, C_MID)
    lcd.print(motion_text, 172, 132, motion_color)

    lcd.fillRect(8, 175, 304, 20, C_BG)
    if data["alerts"]:
        lcd.fillRect(8, 174, 304, 22, 0x2A0000)
        lcd.print("! " + str(data["alerts"][0])[:28], 14, 180, C_RED)

def _draw_data_outdoor():
    lcd.fillRoundRect(9,   29, 302, 64, 5, 0x0A0A1A)
    lcd.fillRoundRect(9,   99, 146, 53, 5, 0x0D0D1A)
    lcd.fillRoundRect(163, 99, 148, 53, 5, 0x0A1A1A)
    lcd.fillRoundRect(9,  159, 302, 46, 5, 0x0D0D0D)

    lcd.print("TEMPERATURE EXT.", 18, 34, C_MID)
    lcd.print("{}".format(data["temp_outdoor"]), 18, 50, C_WARM)
    lcd.print("C", 105, 62, C_WARM)

    feels = data["feels_like"]
    lcd.print("RESSENTI", 18, 104, C_MID)
    lcd.print("{}C".format(feels) if isinstance(feels, float) else str(feels), 18, 120, C_WHITE)

    lcd.print("VENT", 172, 104, C_MID)
    lcd.print("{} m/s".format(data["wind"]), 172, 120, C_ACCENT)

    lcd.print("CONDITIONS", 18, 164, C_MID)
    lcd.print(str(data["description"])[:28], 18, 180, C_WHITE)

def _draw_data_forecast():
    items_y = [34, 94, 154]
    for i, y in enumerate(items_y):
        lcd.fillRoundRect(9, y + 1, 302, 54, 5, 0x0A140A)
        if i < len(data["forecast"]):
            item = data["forecast"][i]
            dt   = str(item.get("datetime", ""))[:10]
            temp = item.get("temperature", "--")
            desc = str(item.get("description", ""))[:22]
            lcd.print(dt, 18, y + 8, C_MID)
            lcd.print("{}C".format(round(temp) if isinstance(temp, float) else temp), 230, y + 8, C_WARM)
            lcd.print(desc, 18, y + 28, C_WHITE)
        else:
            lcd.print("--", 18, y + 18, C_MID)
    if not data["forecast"]:
        lcd.print("Pas de donnees disponibles", 50, 110, C_MID)

def _draw_data_coach():
    lcd.fillRoundRect(9, 29, 302, 168, 5, 0x1A1A00)
    lcd.fillRect(20, 90, 280, 1, C_DIM)
    l1, l2, l3 = get_coach_tip()
    lcd.print(l1, 20, 55, C_YELLOW)
    lcd.print(l2, 20, 100, C_WHITE)
    lcd.print(l3, 20, 130, C_WHITE)

def _draw_motion_only():
    lcd.fillRoundRect(163, 111, 148, 58, 5, 0x1A1A0A)
    motion_text  = "Detecte" if data["motion"] else "Aucun"
    motion_color = C_WARM if data["motion"] else C_GREEN
    lcd.print("MOUVEMENT", 172, 116, C_MID)
    lcd.print(motion_text, 172, 132, motion_color)

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
#  FIX 1 — Settings state flush
#  Atomically resets all settings sub-navigation flags.
#  Called from every code path that exits page 5 so stale
#  flags can never re-lock navigation on subsequent visits.
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
#  Bug A — "object of type 'file' has no len":
#    UIFlow 1 urequests calls len(data) before sending; file
#    objects have no __len__ so data=f always raises.
#    Fix: read into a pre-allocated bytearray of known size,
#    then del + gc immediately after the POST returns.
#
#  Bug B — watchdog on second consecutive call:
#    MIC.deinit() on an already-deinitialized MIC hangs the I2S
#    hardware waiting for a bus that is already idle, causing the
#    watchdog to fire before the timeout completes.
#    Fix: _mic_initialized flag — deinit only when actually live.
#    Also: 8 kHz sample rate → 8 KB DMA buffer (was 32 KB at
#    16 kHz), which survives a fragmented heap on the second call.
# ============================================================
def ask_question():
    global is_recording, _last_drawn_page, _mic_initialized
    is_recording = True
    vibrate()

    lcd.fillScreen(C_BG)
    draw_header("ASK ME", C_PURPLE)
    draw_card(8, 28, 304, 88, 0x0F000F)
    led_set(LED_ORANGE)
    lcd.print("Preparez-vous...", 20, 55, C_YELLOW)
    time.sleep(2)

    try:
        # ── Step 1: Release speaker I2S bus first (NS4168 holds shared bus) ───
        try:
            speaker.deinit()
        except Exception:
            pass
        gc.collect()
        time.sleep_ms(300)

        # ── Step 2: Deinit MIC only if it is currently live ───────────────────
        # Calling MIC.deinit() on an uninitialised MIC hangs the I2S hardware
        # for the full timeout, triggering the watchdog before it returns.
        if _mic_initialized:
            try:
                MIC.deinit(1000)
            except Exception:
                pass
            _mic_initialized = False
            gc.collect()
            time.sleep_ms(500)

        # ── Step 3: Double GC to defragment heap before DMA allocation ────────
        gc.collect()
        time.sleep_ms(200)
        gc.collect()
        time.sleep_ms(300)

        # ── Step 4: Begin MIC at 8 kHz ────────────────────────────────────────
        # 8 kHz: DMA buffer = 8 KB (was 32 KB at 16 kHz) — survives a
        # fragmented heap. Whisper accepts 8 kHz audio without issue.
        MIC.begin(pin_ws=0, pin_data=34, sample_rate_hz=8000,
                  buffer_length_ms=500, block_length_ms=100)
        _mic_initialized = True

        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 28, 304, 88, 0x0F000F)
        led_set(LED_PURPLE)
        lcd.print("Enregistrement 5s...", 20, 45, C_RED)
        lcd.print("Parlez maintenant !", 20, 70, C_WHITE)

        with open('/flash/question.wav', 'wb') as f_mic:
            MIC.recordStart(f_mic, 5000)
            MIC.waitRecordDone(7000)

        # ── Step 5: Release MIC I2S aggressively ─────────────────────────────
        MIC.deinit(2000)
        _mic_initialized = False
        gc.collect()
        time.sleep_ms(500)
        gc.collect()
        time.sleep_ms(500)

        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        draw_card(8, 28, 304, 88, 0x0F000F)
        led_set(LED_ORANGE)
        lcd.print("Traitement...", 20, 55, C_YELLOW)

        # ── Step 6: POST via bytearray — UIFlow 1 urequests rejects file objs ─
        # urequests calls len(data) before sending. File objects have no
        # __len__, so data=f raises "object of type 'file' has no len".
        # bytearray(known_size) pre-allocates one contiguous block; readinto()
        # fills it without a second copy. At 8 kHz × 5 s × 2 B = 80 KB,
        # which a post-GC heap can satisfy in one shot.
        try:
            file_size = uos.stat('/flash/question.wav')[6]
        except Exception:
            file_size = 0
        lcd.print("{}o envoyes".format(file_size), 20, 75, C_MID)

        gc.collect()                              # sweep before large allocation
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
        del buf                                   # free 80 KB immediately
        gc.collect()

        if r.status_code == 200:
            led_set(LED_WHITE)
            lcd.print("Lecture reponse...", 20, 80, C_GREEN)
            with open('/flash/answer.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            del r
            gc.collect()

            time.sleep_ms(500)
            speaker.playWAV('/flash/answer.wav', volume=6)
            lcd.print("Termine !", 20, 105, C_GREEN)

            try:
                speaker.deinit()
            except Exception:
                pass
            gc.collect()
            time.sleep_ms(800)

        else:
            try:
                lcd.print(r.text[:25], 20, 80, C_RED)
            except Exception:
                pass
            r.close()
            led_set(LED_RED)
            lcd.print("Erreur serveur", 20, 80, C_RED)

    except Exception as e:
        lcd.fillScreen(C_BG)
        draw_header("ASK ME", C_PURPLE)
        lcd.print("ERR:{}".format(str(e)[:25]), 20, 100, C_RED)
        led_set(LED_RED)

    finally:
        cleanup_wav()
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
    if now - last_tts_time < 300:   # 5-minute cooldown
        return

    # Build a contextual French announcement from live data.
    # Accented chars are safe: UIFlow 1 uses UTF-8 source files.
    desc = str(data["description"]).lower()
    temp = data["temp_outdoor"]
    wind = data["wind"]
    hum  = data["humidity"]
    aqi  = data["air_quality"]
    try:
        if "rain" in desc or "storm" in desc:
            msg = ("Bonjour coach ! Pluie prevue aujourd'hui. "
                   "Pensez a prevoir des vetements impermeables pour l'entrainement !")
        elif isinstance(temp, (int, float)) and temp > 25:
            msg = ("Bonjour coach ! Il fait {} degres dehors aujourd'hui. "
                   "Faites boire les joueurs toutes les quinze minutes !").format(int(temp))
        elif isinstance(temp, (int, float)) and temp < 5:
            msg = ("Bonjour coach ! Il fait seulement {} degres. "
                   "Prevoyez un echauffement long et progressif avant l'entrainement !").format(int(temp))
        elif isinstance(wind, (int, float)) and wind > 10:
            msg = ("Bonjour coach ! Vent fort de {} metres par seconde. "
                   "Adaptez vos exercices en consequence !").format(round(wind, 1))
        elif isinstance(hum, (int, float)) and hum < 40:
            msg = ("Bonjour coach ! Humidite tres basse, seulement {} pourcent. "
                   "Insistez sur l'hydratation pendant l'entrainement !").format(int(hum))
        elif isinstance(aqi, int) and aqi > 150:
            msg = ("Bonjour coach ! La qualite de l'air est mauvaise aujourd'hui. "
                   "Evitez les efforts cardio intenses !")
        else:
            msg = ("Bonjour coach ! Les conditions sont ideales pour l'entrainement. "
                   "Bonne seance a toute l'equipe !")
    except Exception:
        msg = "Bonjour coach ! Verifiez les conditions avant l'entrainement."

    # POST text to /announce → middleware runs TTS only (no STT/GPT), returns WAV.
    try:
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
            speaker.playWAV('/flash/announce.wav', volume=6)
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
    lcd.fillRoundRect(9, 29, 302, 86, 5, 0x0F000F)
    lcd.print("Appuie sur B", 20, 45, C_WHITE)
    lcd.print("pour poser une question", 20, 68, C_MID)
    lcd.fillRect(8, 122, 304, 1, C_DIM)
    lcd.print("Exemples :", 18, 132, C_MID)
    lcd.print("Good to train today?", 18, 152, C_DIM)
    lcd.print("How is air quality?", 18, 170, C_DIM)
    draw_page_indicator()

def show_page_settings():
    global _last_drawn_page
    _last_drawn_page = 5
    lcd.fillScreen(C_BG)
    draw_header("SETTINGS", C_WHITE)

    if settings_in_keyboard:
        draw_card(8, 28, 304, 42, 0x0A0A1A)
        lcd.print("WiFi : " + settings_keyboard_ssid[:22], 14, 36, C_ACCENT)
        pwd_display = "*" * len(settings_keyboard_password)
        lcd.print("Pass : " + pwd_display[-20:], 14, 54, C_YELLOW)
        lcd.fillRect(8, 76, 304, 1, C_DIM)
        draw_card(85, 87, 60, 28, 0x1A1A00)
        total_k = len(KEYBOARD_LIST)
        prev_i  = (settings_keyboard_index - 1) % total_k
        curr_i  = settings_keyboard_index
        next_i  = (settings_keyboard_index + 1) % total_k
        lcd.print(str(KEYBOARD_LIST[prev_i]), 30, 96, C_MID)
        lcd.print(str(KEYBOARD_LIST[curr_i]), 97, 93, C_YELLOW)
        lcd.print(str(KEYBOARD_LIST[next_i]), 160, 96, C_MID)
        lcd.fillRect(8, 124, 304, 1, C_DIM)
        lcd.print("A: prec   C: suiv   B: select", 14, 134, C_MID)
        lcd.print("Naviguer jusqu'a <OK> pour valider", 14, 154, C_DIM)
        lcd.print("<BS> pour effacer", 14, 172, C_DIM)

    elif settings_in_wifi:
        lcd.print("Reseaux WiFi disponibles", 14, 32, C_ACCENT)
        lcd.fillRect(8, 48, 304, 1, C_DIM)
        all_items = ["< Back"] + settings_wifi_networks
        if len(all_items) == 1:
            lcd.print("Scan en cours...", 14, 80, C_MID)
        else:
            visible_start = max(0, settings_wifi_index - 1) if settings_wifi_index > 1 else 0
            visible = all_items[visible_start:visible_start + 4]
            for i, ssid in enumerate(visible):
                real_i = visible_start + i
                y = 56 + i * 36
                if real_i == settings_wifi_index:
                    draw_card(8, y - 3, 304, 30, 0x0A1A2A)
                    color = C_RED if ssid == "< Back" else C_ACCENT
                    lcd.print("> " + ssid[:26], 16, y + 4, color)
                else:
                    color = 0x884444 if ssid == "< Back" else C_MID
                    lcd.print("  " + ssid[:26], 16, y + 4, color)
        lcd.fillRect(8, 202, 304, 1, C_DIM)
        lcd.print("A/C: naviguer   B: choisir", 14, 210, C_DIM)

    elif settings_menu_active:
        lcd.print("Menu principal", 14, 32, C_MID)
        lcd.fillRect(8, 48, 304, 1, C_DIM)
        for i, item in enumerate(SETTINGS_MENU_ITEMS):
            y = 62 + i * 48
            if i == settings_menu_index:
                draw_card(8, y - 4, 304, 38, 0x0A1A2A)
                lcd.print("> " + item, 20, y + 8, C_ACCENT)
            else:
                lcd.print("  " + item, 20, y + 8, C_MID)
        lcd.fillRect(8, 202, 304, 1, C_DIM)
        lcd.print("A/C: naviguer   B: valider", 14, 210, C_DIM)

    else:
        # Root settings landing view
        draw_card(8,  28, 304, 60, 0x111122)
        lcd.print("WiFi", 20, 36, C_MID)
        wifi_status = "Connecte: " + wlan.ifconfig()[0] if wlan.isconnected() else "Non connecte"
        wifi_color  = C_GREEN if wlan.isconnected() else C_RED
        lcd.print(wifi_status[:28], 20, 54, wifi_color)
        draw_card(8, 94, 304, 58, 0x111122)
        lcd.print("Luminosite", 20, 102, C_MID)
        lcd.print("{}%".format(brightness), 20, 118, C_WHITE)
        lcd.fillRect(20, 138, 260, 6, C_DIM)
        lcd.fillRect(20, 138, int(260 * brightness / 100), 6, C_ACCENT)
        lcd.fillRect(8, 158, 304, 1, C_DIM)
        lcd.print("Appuie sur B pour le menu", 20, 168, C_MID)
        lcd.print("A: retour aux pages", 20, 188, C_DIM)

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
    # FIX 1: Use centralised flush instead of manual piecemeal clears
    _flush_settings_state()
    _last_drawn_page = -1

    lcd.fillScreen(C_BG)
    draw_header("WIFI", C_ACCENT)
    led_set(LED_ORANGE)
    draw_card(8, 30, 304, 100, 0x0A0A1A)
    lcd.print("Connexion a :", 18, 40, C_MID)
    lcd.print(ssid[:28], 18, 58, C_YELLOW)
    lcd.fillRect(18, 78, 280, 1, C_DIM)
    lcd.print("Patientez...", 18, 88, C_MID)

    try:
        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(1)
        wifiCfg.doConnect(ssid, password)
        t0 = time.time()
        while not wlan.isconnected() and time.time() - t0 < 15:
            time.sleep(1)
        if wlan.isconnected():
            led_set(LED_GREEN)
            vibrate_double()
            lcd.print("Connecte !", 18, 115, C_GREEN)
            lcd.print(wlan.ifconfig()[0], 18, 135, C_MID)
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
            lcd.print("Echec connexion", 18, 115, C_RED)
            time.sleep(2)
    except Exception as e:
        led_set(LED_RED)
        lcd.print("ERR:{}".format(str(e)[:25]), 18, 115, C_RED)
        time.sleep(2)

    show_page_settings()

# ============================================================
#  FIX 1 — Navigation: swipe, Button A, Button C, Button B
# ============================================================

def handle_swipe(dx):
    global current_page
    # FIX 1: Block swipe only when inside a settings sub-menu.
    # Root settings (all flags False) now allows swipe to exit the page.
    if current_page == 5 and (settings_menu_active or settings_in_wifi
                               or settings_in_keyboard
                               or settings_editing is not None):
        return
    if dx > SWIPE_THRESHOLD:
        vibrate()
        _flush_settings_state()   # ensure clean state when leaving page 5 via swipe
        current_page = (current_page - 1) % total_pages
        show_current_page()
        led_page(current_page)
    elif dx < -SWIPE_THRESHOLD:
        vibrate()
        _flush_settings_state()
        current_page = (current_page + 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_left_pressed():
    global current_page, settings_menu_index, settings_wifi_index
    global settings_keyboard_index, brightness
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
        else:
            # FIX 1: Root settings view — Button A navigates back to page 4.
            # This was previously a no-op ("A ne fait rien"), causing the lock.
            _flush_settings_state()
            current_page = 4
            show_current_page()
            led_page(current_page)
    else:
        current_page = (current_page - 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_right_pressed():
    global current_page, settings_menu_index, settings_wifi_index
    global settings_keyboard_index, brightness
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
        else:
            # FIX 1: Flush state before leaving settings via right-swipe button
            _flush_settings_state()
            current_page = (current_page + 1) % total_pages
            show_current_page()
            led_page(current_page)
    else:
        current_page = (current_page + 1) % total_pages
        show_current_page()
        led_page(current_page)

def btn_middle_pressed():
    global settings_menu_active, settings_menu_index
    global settings_in_wifi, settings_wifi_networks, settings_wifi_index
    global settings_in_keyboard, settings_keyboard_ssid, settings_keyboard_password
    global settings_keyboard_index, settings_editing, current_page, brightness
    vibrate()

    if current_page == 5:
        if settings_in_keyboard:
            char = KEYBOARD_LIST[settings_keyboard_index]
            if char == "<BS>":
                settings_keyboard_password = settings_keyboard_password[:-1]
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
                    # FIX 1: Use flush helper for consistent sub-state teardown
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
                        # Keep settings_in_wifi True while we note the SSID,
                        # then transition cleanly into keyboard mode.
                        settings_in_wifi = False
                        show_page_settings()

        elif settings_menu_active:
            choice = SETTINGS_MENU_ITEMS[settings_menu_index]
            if choice == "Back":
                # FIX 1: Flush to root settings cleanly
                _flush_settings_state()
                show_page_settings()
            elif choice == "Luminosite":
                # FIX 1: Flush then set only brightness editing flag
                _flush_settings_state()
                settings_editing = "brightness"
                show_page_settings()
            elif choice == "WiFi":
                # FIX 1: Flush then set only wifi flag
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

        elif settings_editing == "brightness":
            # FIX 1: Flush clears settings_editing = None and all other flags
            _flush_settings_state()
            show_page_settings()

        else:
            settings_menu_active = True
            settings_menu_index  = 0
            show_page_settings()

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
lcd.fillRect(0,   0, 320, 3, C_ACCENT)
lcd.fillRect(0, 237, 320, 3, C_ACCENT)
led_set(LED_BLUE)
lcd.print("COACH WEATHER", 55, 75, C_WARM)
lcd.fillRect(55, 97, 210, 1, C_DIM)
lcd.print("v2.0", 138, 107, C_MID)
lcd.print("Demarrage...", 95, 145, C_MID)
vibrate(100)
time.sleep(1)

screen.set_screen_brightness(brightness)

lcd.print("Connexion WiFi...", 85, 168, C_MID)
wifiCfg.autoConnect(lcdShow=True)
time.sleep(1)

lcd.print("Sync NTP...", 105, 188, C_MID)
try:
    rtc.settime('ntp', host='cn.pool.ntp.org', tzone=3)
    lcd.print("OK", 215, 188, C_GREEN)
except:
    lcd.print("FAIL", 215, 188, C_RED)
time.sleep(1)

lcd.print("Chargement...", 95, 208, C_MID)
fetch_latest()
fetch_forecast()
fetch_alerts()

vibrate_double()
show_current_page()
led_page(current_page)

touch_start_x  = None
touch_end_x    = None
last_touch     = False
counter        = 0
_fetch_counter = 0
_motion_prev   = False

# ============================================================
#  MAIN LOOP
# ============================================================
while True:
    time.sleep_ms(100)

    # ── TOUCH ────────────────────────────────────────────────────────────────
    # FIX 1: Evaluate touch.status() inline (avoids stale variable), then
    # guard touch.read() result for None to handle the race window where
    # the finger lifts between status() and read().
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

    counter += 1

    # ── MOTION: read every 500 ms ─────────────────────────────────────────────
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

    # ── FETCH + SEND every 30 s ───────────────────────────────────────────────
    if counter >= 300:
        counter = 0
        if not wlan.isconnected():
            wifiCfg.reconnect()
        send_sensor_data()
        fetch_latest()
        fetch_alerts()
        if current_page == 0:
            _draw_data_indoor()
            draw_page_indicator()
        elif current_page == 1:
            _draw_data_outdoor()
            draw_page_indicator()
        elif current_page == 2:
            _draw_data_forecast()
            draw_page_indicator()
        elif current_page == 3:
            _draw_data_coach()
            draw_page_indicator()

    # ── FORECAST every 5 min ─────────────────────────────────────────────────
    _fetch_counter += 1
    if _fetch_counter >= 3000:
        _fetch_counter = 0
        fetch_forecast()
