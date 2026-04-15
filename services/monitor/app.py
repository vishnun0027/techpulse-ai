import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.db import supabase
from shared.redis_client import redis, STREAM_RAW

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TechPulse AI Monitor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS STYLING ──────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    .main { background-color: #0f172a; }
    .stMetric { background-color: #1e293b; padding: 20px; border-radius: 10px; border: 1px solid #334155; }
    .stPlotlyChart { border-radius: 10px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# ── DATA FETCHING ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_telemetry():
    res = supabase.table("telemetry").select("*").order("timestamp", desc=True).limit(100).execute()
    return pd.DataFrame(res.data)

@st.cache_data(ttl=60)
def fetch_article_counts():
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    
    total = supabase.table("articles").select("count", count="exact").execute().count
    delivered = supabase.table("articles").select("count", count="exact").eq("is_delivered", True).execute().count
    ready = supabase.table("articles").select("count", count="exact").eq("is_delivered", False).gte("created_at", since).gte("score", 2.5).execute().count
    
    return total, delivered, ready

def get_redis_pending():
    try:
        return redis.execute(command=["XLEN", STREAM_RAW]) or 0
    except:
        return "N/A"

# ── HEADER ───────────────────────────────────────────────────────────────────
st.title("🤖 TechPulse AI — System Pulse")
st.markdown("Monitor your tech news pipeline in real-time.")

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.header("Navigation")
action = st.sidebar.radio("View", ["Dashboard", "Telemetry Logs", "Database Explorer"])

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ── DASHBOARD ────────────────────────────────────────────────────────────────
if action == "Dashboard":
    total, delivered, ready = fetch_article_counts()
    pending = get_redis_pending()
    
    # 1. Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending in Stream", pending, help="Articles waiting to be summarized")
    col2.metric("Total in DB", total, help="Lifetime processed articles")
    col3.metric("Total Delivered", delivered, help="Successfully sent to Slack/Discord")
    col4.metric("Ready (Top 24h)", ready, help="High-score articles pending delivery")
    
    st.divider()
    
    # 2. Charts Row
    df = fetch_telemetry()
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("Processing Trends")
            # Extract 'summarized' metric if available
            sum_df = df[df['service'] == 'summarizer'].copy()
            if not sum_df.empty:
                sum_df['count'] = sum_df['metrics'].apply(lambda x: x.get('summarized', 0))
                fig = px.area(sum_df, x='timestamp', y='count', title="Summarized Articles",
                             color_discrete_sequence=['#3b82f6'])
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No summarizer telemetry data yet.")

        with col_chart2:
            st.subheader("Collection Activity")
            coll_df = df[df['service'] == 'collector'].copy()
            if not coll_df.empty:
                coll_df['found'] = coll_df['metrics'].apply(lambda x: x.get('found', 0))
                coll_df['queued'] = coll_df['metrics'].apply(lambda x: x.get('queued', 0))
                fig = px.bar(coll_df, x='timestamp', y=['found', 'queued'], barmode='group',
                            title="Articles Found vs Queued", color_discrete_map={"found": "#94a3b8", "queued": "#10b981"})
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No collector telemetry data yet.")

# ── TELEMETRY LOGS ───────────────────────────────────────────────────────────
elif action == "Telemetry Logs":
    st.subheader("Recent System Events")
    df = fetch_telemetry()
    if not df.empty:
        # Pre-process metrics for display
        df['details'] = df['metrics'].apply(lambda x: str(x))
        st.dataframe(df[['timestamp', 'service', 'success', 'details']], 
                     width="stretch", hide_index=True)
    else:
        st.info("No telemetry logs found.")

# ── DATABASE EXPLORER ────────────────────────────────────────────────────────
elif action == "Database Explorer":
    st.subheader("Latest 50 Articles")
    res = supabase.table("articles").select("*").order("created_at", desc=True).limit(50).execute()
    if res.data:
        art_df = pd.DataFrame(res.data)
        st.dataframe(art_df[['created_at', 'title', 'source', 'score', 'is_delivered']], 
                     width="stretch")
    else:
        st.info("No articles in database.")

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.caption("TechPulse AI v1.5")
