import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://127.0.0.1:5000")

st.set_page_config(
    page_title="Pre-Training Briefing",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Outfit:wght@300;400;500;600;700;800&display=swap');

*, html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    box-sizing: border-box;
}

.stApp {
    background: #080c14;
}

#MainMenu, footer, header { visibility: hidden; }

.block-container {
    padding: 0 5rem 5rem !important;
    max-width: 100% !important;
}

/* ─── TOPBAR ─────────────────────────────────────────── */
.topbar {
    background: #0d1220;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 1rem 5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-left: -5rem !important;
    margin-right: -5rem !important;
}
.topbar-brand {
    font-size: 0.82rem;
    font-weight: 600;
    color: #e2e8f0;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.topbar-location {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    color: #64748b;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.topbar-right {
    display: flex;
    align-items: center;
    gap: 1.25rem;
}
.topbar-time {
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    color: #64748b;
}
.live-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    border: 1px solid rgba(74,222,128,0.25);
    background: rgba(74,222,128,0.07);
    font-family: 'DM Mono', monospace;
    font-size: 0.62rem;
    color: #4ade80;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.live-dot {
    width: 5px; height: 5px;
    background: #4ade80;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.25} }

/* ─── PAGE CONTENT ───────────────────────────────────── */
.page {
    padding-top: 3.5rem;
}

/* ─── HEADER ─────────────────────────────────────────── */
.page-header {
    margin-bottom: 3rem;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
}
.page-date {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    color: #3b82f6;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.page-title {
    font-size: 2.4rem;
    font-weight: 800;
    color: #f1f5f9;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.page-sub {
    font-size: 0.85rem;
    color: #64748b;
    font-weight: 400;
    margin-top: 0.4rem;
}

/* ─── DECISION ───────────────────────────────────────── */
.decision {
    border-radius: 16px;
    padding: 2.25rem 2.75rem;
    margin-bottom: 3.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 2rem;
}
.decision-go     { background:#051209; border:1px solid rgba(74,222,128,0.2); }
.decision-caution{ background:#110d03; border:1px solid rgba(251,191,36,0.2); }
.decision-stop   { background:#110404; border:1px solid rgba(248,113,113,0.2); }

.decision-left { flex: 1; }
.decision-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
    opacity: 0.6;
}
.decision-go     .decision-label { color: #4ade80; }
.decision-caution .decision-label{ color: #fbbf24; }
.decision-stop   .decision-label { color: #f87171; }

.decision-verdict {
    font-size: 1.7rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
}
.decision-go     .decision-verdict { color: #4ade80; }
.decision-caution .decision-verdict{ color: #fbbf24; }
.decision-stop   .decision-verdict { color: #f87171; }

.decision-detail {
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.6rem;
    line-height: 1.55;
}
.decision-precaution {
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    color: #cbd5e1;
    margin-top: 0.5rem;
}

.decision-right {
    display: flex;
    gap: 3rem;
    text-align: right;
    flex-shrink: 0;
}
.dstat-val {
    font-size: 1.9rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.03em;
    line-height: 1;
}
.dstat-lbl {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.35rem;
}

/* ─── SECTION LABEL ──────────────────────────────────── */
.section-label {
    font-family: 'Outfit', sans-serif;
    font-size: 0.8rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 1.5rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}

/* ─── METRIC STRIP ───────────────────────────────────── */
.metric-strip {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 1rem;
    margin-bottom: 3.5rem;
}
.metric-card {
    background: #0d1220;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.5rem 1.5rem 1.3rem;
    position: relative;
    transition: border-color 0.2s;
}
.metric-card:hover {
    border-color: rgba(255,255,255,0.12);
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 1.5rem; right: 1.5rem;
    height: 2px;
    background: var(--accent, #3b82f6);
    opacity: 0.5;
    border-radius: 0 0 2px 2px;
}
.mc-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 1rem;
}
.mc-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: -0.03em;
    line-height: 1;
}
.mc-unit {
    font-size: 0.85rem;
    color: #64748b;
    font-weight: 400;
}
.mc-sub {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #475569;
    margin-top: 0.7rem;
}

/* ─── ALERT ──────────────────────────────────────────── */
.alert-bar {
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.2);
    border-left: 3px solid rgba(239,68,68,0.7);
    border-radius: 10px;
    padding: 1rem 1.5rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #fca5a5;
    margin-bottom: 2.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    letter-spacing: 0.02em;
}

/* ─── FORECAST ───────────────────────────────────────── */
.forecast-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    margin-bottom: 3.5rem;
}
.fc {
    background: #0d1220;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.75rem 1.25rem;
    text-align: center;
    transition: border-color 0.2s;
}
.fc:hover { border-color: rgba(255,255,255,0.12); }
.fc-day {
    font-family: 'DM Mono', monospace;
    font-size: 0.62rem;
    font-weight: 500;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.2rem;
}
.fc-date {
    font-family: 'DM Mono', monospace;
    font-size: 0.58rem;
    color: #94a3b8;
    margin-bottom: 1.1rem;
}
.fc-icon { font-size: 2.2rem; display: block; margin-bottom: 0.9rem; }
.fc-temp {
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin-bottom: 0.4rem;
}
.fc-desc {
    font-family: 'DM Mono', monospace;
    font-size: 0.58rem;
    color: #475569;
    margin-bottom: 0.9rem;
    line-height: 1.5;
}
.fc-pill {
    display: inline-block;
    padding: 0.22rem 0.7rem;
    border-radius: 20px;
    font-family: 'DM Mono', monospace;
    font-size: 0.58rem;
    letter-spacing: 0.06em;
}
.pill-go   { background:rgba(74,222,128,0.1); color:#86efac; border:1px solid rgba(74,222,128,0.2); }
.pill-warn { background:rgba(251,191,36,0.1); color:#fde68a; border:1px solid rgba(251,191,36,0.2); }
.pill-stop { background:rgba(248,113,113,0.1); color:#fca5a5; border:1px solid rgba(248,113,113,0.2); }

/* ─── WEEKLY SUMMARY ─────────────────────────────────── */
.weekly-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 3.5rem;
}
.wcard {
    background: #0d1220;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.75rem 2rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
}
.wcard-icon { font-size: 1.8rem; opacity: 0.9; }
.wcard-val {
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1;
}
.wcard-lbl {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.4rem;
}
.wcard-note {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    margin-top: 0.25rem;
}

/* ─── CHAT ───────────────────────────────────────────── */
.chat-panel {
    background: #0d1220;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 2.25rem 2.25rem 1.75rem;
    margin-bottom: 3.5rem;
}
.chat-msg-you {
    display: inline-block;
    background: #151d30;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px 12px 12px 3px;
    padding: 0.75rem 1.1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #94a3b8;
    max-width: 70%;
    margin-bottom: 0.35rem;
}
.chat-msg-ai {
    background: #0c1628;
    border: 1px solid rgba(59,130,246,0.15);
    border-radius: 12px 12px 3px 12px;
    padding: 1rem 1.25rem;
    font-size: 0.85rem;
    color: #cbd5e1;
    line-height: 1.75;
    margin-bottom: 1.5rem;
}
.chat-who {
    font-family: 'DM Mono', monospace;
    font-size: 0.58rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.35rem;
}

/* ─── STREAMLIT OVERRIDES ────────────────────────────── */
div[data-testid="stSlider"] {
    padding: 0.5rem 0 1.5rem !important;
}
.stTextInput > div > div > input {
    background: #0d1220 !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-radius: 10px !important;
    color: #cbd5e1 !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.78rem !important;
    padding: 0.75rem 1.2rem !important;
    transition: border-color 0.15s !important;
}
.stTextInput > div > div > input:focus {
    border-color: rgba(59,130,246,0.4) !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.08) !important;
}
.stTextInput > div > div > input::placeholder { color: #334155 !important; }
.stButton > button {
    background: #151d30 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #94a3b8 !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.1em !important;
    border-radius: 10px !important;
    padding: 0.75rem 1.5rem !important;
    text-transform: uppercase !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    border-color: rgba(59,130,246,0.35) !important;
    color: #e2e8f0 !important;
    background: #1a2540 !important;
}
[data-testid="stDataFrame"] > div {
    background: #0d1220 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 14px !important;
}
div[data-testid="stSlider"] > div > div > div {
    background: #1e293b !important;
}
</style>
""", unsafe_allow_html=True)

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_latest():
    try:
        r = requests.get(f"{MIDDLEWARE_URL}/latest", timeout=5)
        return r.json() if r.status_code == 200 else None
    except: return None

@st.cache_data(ttl=30)
def fetch_alerts():
    try:
        r = requests.get(f"{MIDDLEWARE_URL}/alerts", timeout=5)
        return r.json() if r.status_code == 200 else []
    except: return []

@st.cache_data(ttl=300)
def fetch_forecast():
    try:
        r = requests.get(f"{MIDDLEWARE_URL}/forecast", timeout=5)
        return r.json() if r.status_code == 200 else []
    except: return []

def fetch_history(hours):
    try:
        r = requests.get(f"{MIDDLEWARE_URL}/history", params={"hours": hours}, timeout=5)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_averages():
    try:
        r = requests.get(f"{MIDDLEWARE_URL}/averages", timeout=5)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

latest      = fetch_latest()
alerts      = fetch_alerts()
forecast    = fetch_forecast()

ICONS = {
    "clear sky":"☀️","few clouds":"🌤️","scattered clouds":"⛅",
    "broken clouds":"🌥️","shower rain":"🌧️","rain":"🌧️",
    "light rain":"🌦️","thunderstorm":"⛈️","snow":"❄️",
    "mist":"🌫️","overcast clouds":"☁️",
}

def aqi_info(v):
    if not isinstance(v,(int,float)): return "—","#334155"
    if v<50:  return "Excellent","#4ade80"
    if v<100: return "Good","#a3e635"
    if v<150: return "Moderate","#fbbf24"
    return "Poor","#f87171"

def temp_col(v):
    if not isinstance(v,(int,float)): return "#334155"
    if v<5:  return "#93c5fd"
    if v<15: return "#60a5fa"
    if v<25: return "#4ade80"
    if v<30: return "#fbbf24"
    return "#f87171"

def fc_suit(item):
    d = item.get("description","").lower()
    t = item.get("temperature",20)
    if any(w in d for w in ["storm","thunderstorm","heavy rain"]): return "stop","❌ Avoid"
    if t<2 or t>30: return "warn","⚠ Caution"
    if "rain" in d: return "warn","⚠ Rain"
    return "go","✅ Train"

# ── TOP BAR ───────────────────────────────────────────────────────────────────
now      = datetime.now()
time_str = now.strftime("%H:%M")
date_str = now.strftime("%A, %d %B %Y").upper()

st.markdown(f"""
<div class="topbar">
  <div style="display:flex;align-items:center;gap:2rem;">
    <div class="topbar-brand">⚽ Coach Weather Assistant</div>
    <div class="topbar-location">📍 Lausanne · Switzerland</div>
  </div>
  <div class="topbar-right">
    <span class="topbar-time">{time_str} CET</span>
    <div class="live-badge"><div class="live-dot"></div>Live</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── PAGE ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="page">', unsafe_allow_html=True)

# Header
st.markdown(f"""
<div class="page-header">
  <div>
    <div class="page-date">{date_str} · Pre-Training Briefing</div>
    <div class="page-title">Today's Conditions Report</div>
    <div class="page-sub">Locker room & pitch — refreshed every 60 seconds</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── TRAINING DECISION ─────────────────────────────────────────────────────────
if latest:
    t_out  = latest.get("temperature_outdoor")
    wind   = latest.get("wind_speed")
    aqi_v  = latest.get("air_quality")
    desc   = str(latest.get("weather_description","")).lower()

    is_storm    = any(w in desc for w in ["storm","thunderstorm","heavy rain"])
    is_frost    = isinstance(t_out,(int,float)) and t_out < 2
    is_heat     = isinstance(t_out,(int,float)) and t_out > 28
    is_poor_air = isinstance(aqi_v,(int,float)) and aqi_v > 150
    is_wind     = isinstance(wind,(int,float)) and wind > 10

    precautions = []
    if is_frost:    precautions.append("❄ Frost — plan extended warm-up (15+ min)")
    if is_heat:     precautions.append("🥵 High heat — hydration every 15 min")
    if is_poor_air: precautions.append("😷 Poor air — avoid intense cardio")
    if is_wind:     precautions.append("💨 Strong wind — adjust set-piece drills")

    prec_html = "".join([f'<div class="decision-precaution">· {p}</div>' for p in precautions])

    aqi_lbl, aqi_col = aqi_info(aqi_v)
    t_disp = f"{round(t_out,1)}°" if isinstance(t_out,(int,float)) else "—"
    w_disp = f"{round(wind,1)}"   if isinstance(wind,(int,float))  else "—"
    a_disp = str(int(aqi_v))      if isinstance(aqi_v,(int,float)) else "—"

    if is_storm or (is_frost and is_poor_air):
        cls, verdict, detail = "decision-stop","Do Not Train Outside","Dangerous conditions — move session indoors."
    elif precautions:
        cls, verdict, detail = "decision-caution","Train With Precautions","Conditions manageable. Follow guidelines below."
    else:
        cls, verdict, detail = "decision-go","Clear to Train","All parameters within safe range. Good session ahead."

    st.markdown(f"""
    <div class="decision {cls}">
      <div class="decision-left">
        <div class="decision-label">Training Decision</div>
        <div class="decision-verdict">{verdict}</div>
        <div class="decision-detail">{detail}</div>
        {prec_html}
      </div>
      <div class="decision-right">
        <div>
          <div class="dstat-val" style="color:{temp_col(t_out)}">{t_disp}</div>
          <div class="dstat-lbl">Pitch</div>
        </div>
        <div>
          <div class="dstat-val" style="color:{aqi_col}">{a_disp}</div>
          <div class="dstat-lbl">AQI · {aqi_lbl}</div>
        </div>
        <div>
          <div class="dstat-val">{w_disp}</div>
          <div class="dstat-lbl">Wind m/s</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Alerts
for alert in alerts:
    st.markdown(f'<div class="alert-bar">⚠ {alert}</div>', unsafe_allow_html=True)

# ── CURRENT READINGS ──────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Current Readings</div>', unsafe_allow_html=True)

if latest:
    t_in  = latest.get("temperature_indoor","—")
    t_out = latest.get("temperature_outdoor","—")
    hum   = latest.get("humidity_indoor","—")
    aqi_v = latest.get("air_quality","—")
    wind  = latest.get("wind_speed","—")
    wdesc = str(latest.get("weather_description","—")).title()

    aqi_lbl, aqi_col = aqi_info(aqi_v)
    hum_col = "#f87171" if isinstance(hum,(int,float)) and hum<40 else \
              "#fbbf24" if isinstance(hum,(int,float)) and hum<50 else "#e2e8f0"

    ti_disp = f"{round(t_in,1)}"  if isinstance(t_in,(int,float))  else "—"
    to_disp = f"{round(t_out,1)}" if isinstance(t_out,(int,float)) else "—"
    hm_disp = f"{round(hum,1)}"   if isinstance(hum,(int,float))   else "—"
    wi_disp = f"{round(wind,1)}"  if isinstance(wind,(int,float))  else "—"

    st.markdown(f"""
    <div class="metric-strip">
      <div class="metric-card" style="--accent:#f87171;">
        <div class="mc-label">🌡 Indoor Temp</div>
        <div class="mc-value">{ti_disp}<span class="mc-unit">°C</span></div>
        <div class="mc-sub">Locker room</div>
      </div>
      <div class="metric-card" style="--accent:{temp_col(t_out)};">
        <div class="mc-label">🏟 Pitch Temp</div>
        <div class="mc-value" style="color:{temp_col(t_out)}">{to_disp}<span class="mc-unit">°C</span></div>
        <div class="mc-sub">Outdoor</div>
      </div>
      <div class="metric-card" style="--accent:{hum_col};">
        <div class="mc-label">💧 Humidity</div>
        <div class="mc-value" style="color:{hum_col}">{hm_disp}<span class="mc-unit">%</span></div>
        <div class="mc-sub">{'⚠ Hydrate players' if isinstance(hum,(int,float)) and hum<40 else 'Locker room'}</div>
      </div>
      <div class="metric-card" style="--accent:{aqi_col};">
        <div class="mc-label">💨 Air Quality</div>
        <div class="mc-value" style="color:{aqi_col}">{int(aqi_v) if isinstance(aqi_v,(int,float)) else '—'}</div>
        <div class="mc-sub">{aqi_lbl}</div>
      </div>
      <div class="metric-card" style="--accent:#a78bfa;">
        <div class="mc-label">🌬 Wind</div>
        <div class="mc-value">{wi_disp}<span class="mc-unit"> m/s</span></div>
        <div class="mc-sub">{'⚠ Strong' if isinstance(wind,(int,float)) and wind>10 else 'Outdoor'}</div>
      </div>
      <div class="metric-card" style="--accent:#60a5fa;">
        <div class="mc-label">☁ Conditions</div>
        <div class="mc-value" style="font-size:1rem;padding-top:0.55rem;font-family:'Outfit',sans-serif;font-weight:600;color:#94a3b8;">{wdesc}</div>
        <div class="mc-sub">Current weather</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── WEEK AHEAD ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Week Ahead — Pitch Forecast</div>', unsafe_allow_html=True)

if forecast and not isinstance(forecast, dict):
    daily = forecast[::8][:5]
    html  = '<div class="forecast-row">'
    for item in daily:
        icon = ICONS.get(item["description"].lower(),"🌡️")
        tc   = temp_col(item["temperature"])
        suit, suit_lbl = fc_suit(item)
        try:
            d = datetime.strptime(item["datetime"].split(" ")[0],"%Y-%m-%d")
            day_name = d.strftime("%a").upper()
            day_date = d.strftime("%d %b")
        except:
            day_name = "—"; day_date = ""
        html += f"""
        <div class="fc">
          <div class="fc-day">{day_name}</div>
          <div class="fc-date">{day_date}</div>
          <span class="fc-icon">{icon}</span>
          <div class="fc-temp" style="color:{tc}">{round(item['temperature'])}°C</div>
          <div class="fc-desc">{item['description'].title()}</div>
          <div class="fc-pill pill-{suit}">{suit_lbl}</div>
        </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ── HISTORICAL DATA ───────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Locker Room — Historical Data</div>', unsafe_allow_html=True)

hours = st.slider("", min_value=1, max_value=72, value=24, format="%dh")
df    = fetch_history(hours)

BG, GRID, FC = "#0d1120", "rgba(255,255,255,0.03)", "#1e293b"
AXIS = dict(gridcolor=GRID, showgrid=True, zeroline=False,
            tickfont=dict(size=9, color=FC, family="DM Mono"),
            linecolor="rgba(255,255,255,0.03)")

if not df.empty:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["temperature_indoor"], mode="lines",
            line=dict(color="#f87171", width=1.5),
            fill="tozeroy", fillcolor="rgba(248,113,113,0.03)"
        ))
        fig.update_layout(
            title=dict(text="Indoor Temperature (°C)", font=dict(color=FC,size=10,family="DM Mono"), x=0),
            paper_bgcolor=BG, plot_bgcolor=BG,
            font=dict(color=FC, family="DM Mono", size=9),
            xaxis=AXIS, yaxis=AXIS,
            margin=dict(l=4,r=4,t=32,b=4), height=280, showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df["timestamp"], y=df["humidity_indoor"], mode="lines",
            line=dict(color="#38bdf8", width=1.5),
            fill="tozeroy", fillcolor="rgba(56,189,248,0.03)"
        ))
        fig2.add_hline(y=40, line_dash="dot", line_color="rgba(248,113,113,0.3)",
            annotation_text="Min 40%",
            annotation_font=dict(color="rgba(248,113,113,0.5)", size=8, family="DM Mono"))
        fig2.update_layout(
            title=dict(text="Indoor Humidity (%)", font=dict(color=FC,size=10,family="DM Mono"), x=0),
            paper_bgcolor=BG, plot_bgcolor=BG,
            font=dict(color=FC, family="DM Mono", size=9),
            xaxis=AXIS, yaxis=AXIS,
            margin=dict(l=4,r=4,t=32,b=4), height=280, showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)

    fig3 = go.Figure()
    aqi_colors = ['#f87171' if v>150 else '#fbbf24' if v>100 else '#4ade80'
                  for v in df["air_quality"]]
    fig3.add_trace(go.Bar(x=df["timestamp"], y=df["air_quality"],
                          marker_color=aqi_colors, marker_opacity=0.7))
    for y, col, lbl in [(100,"rgba(251,191,36,0.25)","Moderate · 100"),
                         (150,"rgba(248,113,113,0.25)","Poor · 150")]:
        fig3.add_hline(y=y, line_dash="dot", line_color=col,
            annotation_text=lbl,
            annotation_font=dict(color=col, size=8, family="DM Mono"))
    fig3.update_layout(
        title=dict(text="Air Quality Index (AQI)", font=dict(color=FC,size=10,family="DM Mono"), x=0),
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=FC, family="DM Mono", size=9),
        xaxis=AXIS, yaxis=AXIS,
        margin=dict(l=4,r=4,t=32,b=4), height=260, showlegend=False,
        bargap=0.15
    )
    st.plotly_chart(fig3, use_container_width=True)

else:
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;color:#475569;padding:3rem 0 2rem;">No historical data yet — run the simulator to populate.</div>', unsafe_allow_html=True)

# ── WEEKLY SUMMARY ────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Weekly Summary — 7-Day Averages</div>', unsafe_allow_html=True)

daily_avg = fetch_averages()
if not daily_avg.empty:
    avg_t = round(daily_avg["avg_temp_indoor"].mean(),1)  if "avg_temp_indoor"  in daily_avg.columns else None
    avg_h = round(daily_avg["avg_humidity"].mean(),1)     if "avg_humidity"     in daily_avg.columns else None
    avg_a = round(daily_avg["avg_air_quality"].mean(),0)  if "avg_air_quality"  in daily_avg.columns else None

    _, ac  = aqi_info(avg_a)
    hc     = "#f87171" if isinstance(avg_h,(int,float)) and avg_h<40 else \
             "#fbbf24" if isinstance(avg_h,(int,float)) and avg_h<50 else "#e2e8f0"
    hn     = "⚠ Below safe" if isinstance(avg_h,(int,float)) and avg_h<40 else "7-day avg"
    albl,_ = aqi_info(avg_a)

    st.markdown(f"""
    <div class="weekly-row">
      <div class="wcard">
        <div class="wcard-icon">🌡</div>
        <div>
          <div class="wcard-val" style="color:{temp_col(avg_t)}">{avg_t if avg_t else '—'}°C</div>
          <div class="wcard-lbl">Avg Indoor Temp</div>
          <div class="wcard-note" style="color:#475569;">7-day average</div>
        </div>
      </div>
      <div class="wcard">
        <div class="wcard-icon">💧</div>
        <div>
          <div class="wcard-val" style="color:{hc}">{avg_h if avg_h else '—'}%</div>
          <div class="wcard-lbl">Avg Humidity</div>
          <div class="wcard-note" style="color:{'#f87171' if isinstance(avg_h,(int,float)) and avg_h<40 else '#1e293b'};">{hn}</div>
        </div>
      </div>
      <div class="wcard">
        <div class="wcard-icon">💨</div>
        <div>
          <div class="wcard-val" style="color:{ac}">{int(avg_a) if avg_a else '—'}</div>
          <div class="wcard-lbl">Avg Air Quality</div>
          <div class="wcard-note" style="color:{ac};">{albl}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown('<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;color:#475569;padding:1rem 0 2rem;">Not enough data yet.</div>', unsafe_allow_html=True)

# ── COACH Q&A ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Ask Your Weather Assistant</div>', unsafe_allow_html=True)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

ci, cb = st.columns([5, 1])
with ci:
    q = st.text_input("q", placeholder="e.g. 'Is it safe to train outside today?' · 'What was the humidity yesterday?'", label_visibility="collapsed")
with cb:
    ask = st.button("Ask →")

if ask and q:
    with st.spinner(""):
        try:
            r = requests.post(f"{MIDDLEWARE_URL}/ask", json={"question": q}, timeout=15)
            ans = r.json().get("answer","Sorry, couldn't get an answer.")
        except Exception as e:
            ans = f"Connection error: {e}"
    st.session_state.chat_history.append({"q": q, "a": ans})

for chat in reversed(st.session_state.chat_history):
    st.markdown(f'<div class="chat-who">You</div><div class="chat-msg-you">{chat["q"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-who">Assistant</div><div class="chat-msg-ai">{chat["a"]}</div>', unsafe_allow_html=True)


# ── FOOTER ────────────────────────────────────────────────────────────────────
updated = datetime.now().strftime("%d %b %Y · %H:%M")
st.markdown(f"""
<div style="padding-top:1.75rem;border-top:1px solid rgba(255,255,255,0.07);
     display:flex;justify-content:space-between;align-items:center;">
  <span style="font-family:'DM Mono',monospace;font-size:0.62rem;color:#475569;">
    Coach Weather Assistant · HEC Lausanne · IoT Cloud Project 2026
  </span>
  <span style="font-family:'DM Mono',monospace;font-size:0.62rem;color:#475569;">
    Updated {updated} · Flask · BigQuery · OpenAI · OpenWeatherMap
  </span>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)