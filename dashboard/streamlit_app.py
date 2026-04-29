import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'middleware'))

import streamlit as st
import plotly.express as px
import pandas as pd
from bigquery_client import get_historical_data, get_latest_reading, get_daily_averages, check_alerts

st.set_page_config(
    page_title="Home Weather Monitor",
    page_icon="🌤️",
    layout="wide"
)

st.title("🌤️ Home Weather Monitor")
st.caption("Live indoor & outdoor conditions — Lausanne")


st.cache_data.clear()



# --- Latest reading ---
latest = get_latest_reading()

if latest:
    alerts = check_alerts(latest)
    for alert in alerts:
        st.warning(alert)

    st.subheader("Current conditions")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Indoor temp", f"{latest.get('temperature_indoor', 'N/A')}°C")
    col2.metric("💧 Humidity", f"{latest.get('humidity_indoor', 'N/A')}%")
    col3.metric("💨 Air quality", latest.get('air_quality', 'N/A'))
    col4.metric("🌍 Outdoor temp", f"{latest.get('temperature_outdoor', 'N/A')}°C")

    col5, col6 = st.columns(2)
    col5.metric("🌬️ Wind speed", f"{latest.get('wind_speed', 'N/A')} m/s")
    col6.metric("☁️ Weather", latest.get('weather_description', 'N/A'))
else:
    st.info("No data yet — make sure the simulator is running.")

st.divider()

# --- Historical charts ---
st.subheader("Historical data")

hours = st.slider("Show last N hours", min_value=1, max_value=72, value=24)
df = get_historical_data(hours)

if not df.empty:
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig_temp = px.line(
        df, x="timestamp", y="temperature_indoor",
        title="Indoor temperature (°C)",
        labels={"temperature_indoor": "°C", "timestamp": "Time"}
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
st.subheader("7-day averages")
daily = get_daily_averages(7)

if not daily.empty:
    st.dataframe(daily, use_container_width=True)
else:
    st.info("Not enough data for daily averages yet.")