import os
import streamlit as st
import plotly.express as px
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
# MIDDLEWARE_URL is read from .env so it works both locally and on the cloud
# Locally: http://127.0.0.1:5000
# On Cloud Run: your deployed Flask URL
MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://127.0.0.1:5000")

st.set_page_config(
    page_title="⚽ Coach Weather Assistant",
    page_icon="⚽",
    layout="wide"
)

# --- Header ---
st.title("⚽ Coach Weather Assistant")
st.caption("Indoor locker room & outdoor pitch conditions — Lausanne")

# --- Fetch latest data from Flask (not BigQuery directly) ---
try:
    latest_response = requests.get(f"{MIDDLEWARE_URL}/latest", timeout=5)
    latest = latest_response.json() if latest_response.status_code == 200 else None
except Exception:
    latest = None

# --- Fetch alerts from Flask ---
try:
    alerts_response = requests.get(f"{MIDDLEWARE_URL}/alerts", timeout=5)
    alerts = alerts_response.json() if alerts_response.status_code == 200 else []
except Exception:
    alerts = []

# --- Show alerts ---
for alert in alerts:
    st.warning(alert)

# --- Current conditions ---
if latest:
    st.subheader("Current conditions")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Indoor temp", f"{latest.get('temperature_indoor', 'N/A')}°C")
    col2.metric("💧 Humidity", f"{latest.get('humidity_indoor', 'N/A')}%")
    col3.metric("💨 Air quality (AQI)", latest.get('air_quality', 'N/A'))
    col4.metric("🌍 Outdoor temp", f"{latest.get('temperature_outdoor', 'N/A')}°C")

    col5, col6 = st.columns(2)
    col5.metric("🌬️ Wind speed", f"{latest.get('wind_speed', 'N/A')} m/s")
    col6.metric("☁️ Weather", str(latest.get('weather_description', 'N/A')).title())
else:
    st.info("No data yet — make sure Flask is running and the simulator has sent some data.")

st.divider()

# --- Outdoor activity conditions badge ---
st.subheader("🏟️ Pitch conditions for training")

outdoor_temp = latest.get("temperature_outdoor") if latest else None
aqi = latest.get("air_quality") if latest else None
wind = latest.get("wind_speed") if latest else None
description = str(latest.get("weather_description", "")).lower() if latest else ""

if outdoor_temp is not None and aqi is not None:
    # Determine condition based on rules
    is_storm = any(word in description for word in ["storm", "thunderstorm", "heavy rain"])
    is_frost = outdoor_temp < 2
    is_heat = outdoor_temp > 28
    is_poor_air = aqi > 150
    is_strong_wind = wind is not None and wind > 10

    if is_storm or (is_frost and is_poor_air):
        st.error("🔴 NOT RECOMMENDED — Dangerous conditions for outdoor training")
    elif is_frost or is_heat or is_poor_air or is_strong_wind:
        st.warning("🟡 CAUTION — Training possible but take precautions")
        if is_frost:
            st.caption("❄️ Frost risk — plan an extended warm-up")
        if is_heat:
            st.caption("🥵 High heat — schedule hydration breaks every 15 min")
        if is_poor_air:
            st.caption("😷 Poor air quality — avoid intense cardio")
        if is_strong_wind:
            st.caption("💨 Strong wind — adjust drills accordingly")
    else:
        st.success("🟢 FAVORABLE — Good conditions for training")
else:
    st.info("Waiting for data to assess pitch conditions...")

st.divider()

# --- Forecast ---
st.subheader("📅 5-day weather forecast")

WEATHER_ICONS = {
    "clear sky": "☀️",
    "few clouds": "🌤️",
    "scattered clouds": "⛅",
    "broken clouds": "🌥️",
    "shower rain": "🌧️",
    "rain": "🌧️",
    "light rain": "🌦️",
    "thunderstorm": "⛈️",
    "snow": "❄️",
    "mist": "🌫️",
    "overcast clouds": "☁️",
}

try:
    forecast_response = requests.get(f"{MIDDLEWARE_URL}/forecast", timeout=5)
    forecast_data = forecast_response.json()

    if forecast_data and not isinstance(forecast_data, dict):
        # Take one reading per day (every 8 entries = 24 hours)
        daily_forecast = forecast_data[::8][:5]
        cols = st.columns(len(daily_forecast))
        for i, item in enumerate(daily_forecast):
            icon = WEATHER_ICONS.get(item['description'], "🌡️")
            date = item['datetime'].split(" ")[0]
            with cols[i]:
                st.markdown(f"**{date}**")
                st.markdown(f"# {icon}")
                st.markdown(f"**{round(item['temperature'])}°C**")
                st.caption(item['description'].title())
except Exception:
    st.info("Forecast unavailable — check your OpenWeatherMap API key.")

st.divider()

# --- Historical charts ---
st.subheader("📈 Historical data")

hours = st.slider("Show last N hours", min_value=1, max_value=72, value=24)

try:
    history_response = requests.get(
        f"{MIDDLEWARE_URL}/history",
        params={"hours": hours},
        timeout=5
    )
    df = pd.DataFrame(history_response.json())
except Exception:
    df = pd.DataFrame()

if not df.empty:
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig_temp = px.line(
        df, x="timestamp", y="temperature_indoor",
        title="Indoor temperature (°C)",
        labels={"temperature_indoor": "°C", "timestamp": "Time"},
        color_discrete_sequence=["#ff6b6b"]
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    fig_humidity = px.line(
        df, x="timestamp", y="humidity_indoor",
        title="Indoor humidity (%)",
        labels={"humidity_indoor": "%", "timestamp": "Time"},
        color_discrete_sequence=["#00b4d8"]
    )
    st.plotly_chart(fig_humidity, use_container_width=True)

    fig_air = px.bar(
        df, x="timestamp", y="air_quality",
        title="Air quality index (AQI)",
        labels={"air_quality": "AQI", "timestamp": "Time"},
        color_discrete_sequence=["#e63946"]
    )
    st.plotly_chart(fig_air, use_container_width=True)

else:
    st.info("No historical data yet.")

st.divider()

# --- Daily averages ---
st.subheader("📊 7-day averages")

try:
    daily_response = requests.get(f"{MIDDLEWARE_URL}/averages", timeout=5)
    daily = pd.DataFrame(daily_response.json())
except Exception:
    daily = pd.DataFrame()

if not daily.empty:
    st.dataframe(daily, use_container_width=True)
else:
    st.info("Not enough data for daily averages yet.")

st.divider()

# --- Q&A Chat ---
st.subheader("🎙️ Ask about conditions")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.text_input(
    "Ask a question (e.g. 'Is it safe to train outside today?')",
    key="question_input"
)

if st.button("Ask") and question:
    with st.spinner("Thinking..."):
        try:
            r = requests.post(
                f"{MIDDLEWARE_URL}/ask",
                json={"question": question},
                timeout=15
            )
            answer = r.json().get("answer", "Sorry, I couldn't answer that.")
        except Exception as e:
            answer = f"Error connecting to assistant: {e}"

    st.session_state.chat_history.append({"q": question, "a": answer})

for chat in reversed(st.session_state.chat_history):
    st.markdown(f"**You:** {chat['q']}")
    st.markdown(f"**Assistant:** {chat['a']}")
    st.markdown("---")