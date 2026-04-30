import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'middleware'))

import streamlit as st
import plotly.express as px
import pandas as pd
import requests
from bigquery_client import get_historical_data, get_latest_reading, get_daily_averages, check_alerts

st.set_page_config(
    page_title="Home Weather Monitor",
    page_icon="🌤️",
    layout="wide"
)

MIDDLEWARE_URL = "http://127.0.0.1:5000"

# --- Header ---
st.title("🌤️ Home Weather Monitor")
st.caption("Live indoor & outdoor conditions — Lausanne")

# --- Alerts ---
latest = get_latest_reading()

if latest:
    alerts = check_alerts(latest)
    for alert in alerts:
        st.warning(alert)

    # --- Current conditions ---
    st.subheader("Current conditions")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Indoor temp", f"{latest.get('temperature_indoor', 'N/A')}°C")
    col2.metric("💧 Humidity", f"{latest.get('humidity_indoor', 'N/A')}%")
    col3.metric("💨 Air quality", latest.get('air_quality', 'N/A'))
    col4.metric("🌍 Outdoor temp", f"{latest.get('temperature_outdoor', 'N/A')}°C")

    col5, col6 = st.columns(2)
    col5.metric("🌬️ Wind speed", f"{latest.get('wind_speed', 'N/A')} m/s")
    col6.metric("☁️ Weather", latest.get('weather_description', 'N/A').title())

else:
    st.info("No data yet — make sure the simulator is running.")

st.divider()

# --- Forecast ---
st.subheader("📅 Weather forecast")

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
    forecast_response = requests.get(f"{MIDDLEWARE_URL}/forecast")
    forecast_data = forecast_response.json()

    if forecast_data:
        # Show one entry per day (every 8 entries = 24 hours)
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
except Exception as e:
    st.info("Forecast unavailable")

st.divider()

# --- Historical charts ---
st.subheader("📈 Historical data")

hours = st.slider("Show last N hours", min_value=1, max_value=72, value=24)
df = get_historical_data(hours)

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
        title="Air quality index",
        labels={"air_quality": "AQI", "timestamp": "Time"},
        color_discrete_sequence=["#e63946"]
    )
    st.plotly_chart(fig_air, use_container_width=True)

else:
    st.info("No historical data yet.")

st.divider()

# --- Daily averages ---
st.subheader("📊 7-day averages")
daily = get_daily_averages(7)

if not daily.empty:
    st.dataframe(daily, use_container_width=True)
else:
    st.info("Not enough data for daily averages yet.")

st.divider()

# --- Q&A Chat ---
st.subheader("🎙️ Ask about your home")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.text_input("Ask a question (e.g. 'What was the humidity yesterday?')", key="question_input")

if st.button("Ask") and question:
    with st.spinner("Thinking..."):
        try:
            r = requests.post(
                f"{MIDDLEWARE_URL}/ask",
                json={"question": question}
            )
            answer = r.json().get("answer", "Sorry, I couldn't answer that.")
        except Exception as e:
            answer = f"Error: {e}"

    st.session_state.chat_history.append({"q": question, "a": answer})

# Display chat history
for chat in reversed(st.session_state.chat_history):
    st.markdown(f"**You:** {chat['q']}")
    st.markdown(f"**Assistant:** {chat['a']}")
    st.markdown("---")