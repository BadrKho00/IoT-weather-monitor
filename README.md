# IoT Pre-Training Briefing Station

An end-to-end IoT system that gives a football coach a real-time briefing on indoor and outdoor conditions before every training session — displayed on an M5Stack Core2 device, stored in Google BigQuery, and visualised in a Streamlit dashboard.

**Demo video:** https://youtu.be/vGcL3AfFn3E

**GitHub repository:** https://github.com/BadrKho00/IoT-weather-monitor

---

## Architecture

```
M5Stack Core2 (device)
  ├─ ENV III sensor  → temperature, humidity
  ├─ TVOC/SGP30      → air quality (eCO2 → AQI proxy)
  └─ PIR sensor      → motion detection

        │  POST /data (JSON)
        ▼

Flask Middleware  ─── Google Cloud Run ───────────────────────────────────────
  ├─ Enriches with OpenWeatherMap outdoor weather
  ├─ Stores enriched row in BigQuery
  ├─ Voice pipeline: Whisper STT → GPT-4o → OpenAI TTS (returns WAV)
  └─ Checks alert thresholds and returns them to the device

        │  BigQuery read
        ▼

Streamlit Dashboard  ── Streamlit Community Cloud ───────────────────────────
  └─ Charts, live readings, 5-day forecast, AI voice Q&A panel
```

---

## Live Deployments

| Component  | URL |
|------------|-----|
| Middleware (Cloud Run) | `https://iot-weather-middleware-183604469593.europe-west6.run.app` |
| Dashboard (Streamlit Cloud) | `https://iot-weather-monitor-pbjyaj2ztt8pumj5fcunqg.streamlit.app/` |

---

## Project Structure

```
├── middleware/           Flask API deployed on Google Cloud Run
│   ├── app.py            Route definitions (POST /data, GET /latest, /forecast, /voice_raw …)
│   ├── bigquery_client.py  BigQuery read/write helpers
│   ├── weather.py        OpenWeatherMap integration
│   ├── voice.py          Whisper STT + GPT-4o + OpenAI TTS pipeline
│   ├── Dockerfile        Container image for Cloud Run
│   └── requirements.txt
│
├── dashboard/            Streamlit dashboard
│   ├── streamlit_app.py  Single-page dashboard (live readings, charts, voice Q&A)
│   └── requirements.txt
│
├── device/               M5Stack Core2 MicroPython code
│   ├── coach_weather.py  ★ All-in-one UIFlow file — upload this to the device
│   ├── config.py         Constants and WiFi credential helpers (modular reference)
│   ├── boot.py           WiFi connect + NTP sync on power-on (modular reference)
│   ├── main.py           Main event loop (modular reference)
│   ├── sensors.py        ENV III / SGP30 / PIR reads (modular reference)
│   ├── api_client.py     HTTP calls to middleware (modular reference)
│   ├── display.py        Screen rendering functions (modular reference)
│   ├── voice.py          Microphone recording + speaker playback (modular reference)
│   └── wifi_setup.py     AP-mode WiFi credential change UI (modular reference)
│
├── requirements.txt      Root requirements for Streamlit Cloud
├── .gitignore
└── Cloud Analytics - Project.pdf
```

> **Device note:** `coach_weather.py` is the production file — it runs everything in a single script for UIFlow compatibility (UIFlow 1.x executes one file). The other files in `device/` are a modular reference implementation showing clean separation of concerns.

---

## Environment Variables

Create a `.env` file (never commit it) in `middleware/` with:

```env
# Google Cloud
GOOGLE_CLOUD_PROJECT=mscis-488614
BIGQUERY_DATASET=weather_monitor
BIGQUERY_TABLE=sensor_data

# OpenWeatherMap
OPENWEATHER_API_KEY=<your_key>
CITY=Lausanne
COUNTRY_CODE=CH

# OpenAI (Whisper + GPT-4o + TTS)
OPENAI_API_KEY=<your_key>
```

For the dashboard, set `MIDDLEWARE_URL` in Streamlit Cloud secrets:

```toml
MIDDLEWARE_URL = "https://iot-weather-middleware-183604469593.europe-west6.run.app"
```

---

## Middleware — Local Development

```bash
cd middleware
pip install -r requirements.txt
python app.py          # runs on http://127.0.0.1:5000
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/health` | Liveness check |
| POST | `/data` | Ingest sensor reading (enriches with weather, stores in BigQuery) |
| GET  | `/latest` | Most recent enriched row from BigQuery |
| GET  | `/history?hours=24` | Time-series rows for the last N hours |
| GET  | `/averages?days=7` | Daily averages for the last N days |
| GET  | `/forecast` | 5-day / 3-hour forecast from OpenWeatherMap |
| GET  | `/alerts` | Active alert list based on latest reading |
| POST | `/ask` | Text Q&A via GPT-4o `{"question": "..."}` |
| POST | `/voice_raw` | Raw WAV in → Whisper → GPT-4o → TTS → WAV out |
| POST | `/announce` | Text-to-speech only `{"text": "..."}` → WAV |

### Deploy to Cloud Run

```bash
cd middleware
gcloud run deploy iot-weather-middleware \
  --source . \
  --region europe-west6 \
  --allow-unauthenticated
```

---

## Dashboard — Local Development

```bash
cd dashboard
pip install -r requirements.txt
MIDDLEWARE_URL=http://127.0.0.1:5000 streamlit run streamlit_app.py
```

---

## Device — Upload to M5Stack Core2

1. Open [flow.m5stack.com](https://flow.m5stack.com) and connect Core2 via USB
2. Upload `device/coach_weather.py` to the device filesystem and name it `main.py`
3. In UIFlow, switch the device to **App mode** (so it auto-runs on power-up)
4. Power-cycle — the device connects to WiFi using credentials stored in `/flash/uiflow/config.json`

### On-Device Features

| Feature | How to trigger |
|---------|---------------|
| Live indoor readings | Always on Page 1 — updates every second |
| Outdoor weather | Fetched from middleware on boot and every 30 s |
| 5-day forecast | Button A → forecast page; refreshed every 30 min |
| Voice Q&A | Button B → speak → AI answers in audio |
| Motion announcement | PIR sensor — fires TTS announcement (max once per hour) |
| WiFi credential change | Button C hold 3 s → on-screen keyboard; or AP mode fallback |

### BigQuery Schema

| Field | Type | Source |
|-------|------|--------|
| `timestamp` | TIMESTAMP | Middleware (UTC) |
| `temperature_indoor` | FLOAT | ENV III sensor |
| `humidity_indoor` | FLOAT | ENV III sensor |
| `air_quality` | INTEGER | SGP30 eCO2 → AQI proxy |
| `motion_detected` | BOOLEAN | PIR sensor |
| `temperature_outdoor` | FLOAT | OpenWeatherMap |
| `humidity_outdoor` | FLOAT | OpenWeatherMap |
| `weather_description` | STRING | OpenWeatherMap |
| `wind_speed` | FLOAT | OpenWeatherMap |

---

## Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Indoor temperature | > 28 °C | > 32 °C |
| Humidity | > 70 % | > 85 % |
| Air quality (AQI) | > 100 | > 200 |
| Outdoor temperature | < 5 °C or > 35 °C | — |
