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

def get_redis_stats():
    try:
        # True lag: messages not yet read by the consumer group
        info = redis.execute(command=["XINFO", "GROUPS", STREAM_RAW])
        lag     = 0
        pending = 0
        if info:
            fields = info[0]
            d = {fields[i]: fields[i+1] for i in range(0, len(fields), 2)}
            lag     = d.get("lag", 0)
            pending = d.get("pending", 0)
        return lag, pending
    except Exception:
        return "N/A", "N/A"

# ── HEADER ───────────────────────────────────────────────────────────────────
st.title("🤖 TechPulse AI — System Pulse")
st.markdown("Monitor your tech news pipeline in real-time.")

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.header("Navigation")
action = st.sidebar.radio("View", ["Dashboard", "Telemetry Logs", "Database Explorer", "⚙️ Settings"])

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ── DASHBOARD ────────────────────────────────────────────────────────────────
if action == "Dashboard":
    total, delivered, ready = fetch_article_counts()
    lag, stuck = get_redis_stats()
    
    # 1. Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Unread in Queue", lag, help="Articles waiting to be processed by Summarizer")
    col2.metric("Stuck (Unacked)", stuck, help="Messages read but not yet acknowledged (retry pending)")
    col3.metric("Total in DB", total, help="Lifetime processed articles")
    col4.metric("Total Delivered", delivered, help="Successfully sent to Slack/Discord")
    col5.metric("Ready (Top 24h)", ready, help="High-score articles pending delivery")
    
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

# ── SETTINGS ──────────────────────────────────────────────────────────────────
elif action == "⚙️ Settings":
    st.subheader("System Configuration")
    
    tab_sources, tab_topics = st.tabs(["📡 RSS Sources", "🔍 Topic Filters"])
    
    with tab_sources:
        st.markdown("### Manage RSS Feeds")
        
        # Fetch current sources
        sources_res = supabase.table("rss_sources").select("*").order("name").execute()
        sources_df = pd.DataFrame(sources_res.data)
        
        if not sources_df.empty:
            for _, row in sources_df.iterrows():
                col_name, col_url, col_status, col_btn = st.columns([2, 5, 1, 1])
                col_name.write(f"**{row['name']}**")
                col_url.code(row['url'])
                status_label = "✅ Active" if row['is_active'] else "❌ Inactive"
                col_status.write(status_label)
                if col_btn.button("🗑️", key=f"del_{row['id']}"):
                    supabase.table("rss_sources").delete().eq("id", row['id']).execute()
                    st.success(f"Deleted {row['name']}")
                    st.rerun()
        else:
            st.info("No sources configured.")
            
        st.divider()
        st.markdown("#### Add New Source")
        with st.form("add_source"):
            new_name = st.text_input("Name (e.g. HackerNews)")
            new_url = st.text_input("RSS URL")
            if st.form_submit_button("Add Source"):
                if new_name and new_url:
                    supabase.table("rss_sources").insert({"name": new_name, "url": new_url}).execute()
                    st.success(f"Added {new_name}")
                    st.rerun()
                else:
                    st.error("Please provide both name and URL.")

    with tab_topics:
        st.markdown("### Topic Filtering")
        st.info("The Collector uses these keywords to keep your feed relevant. Separate multiple topics with commas.")
        
        # Fetch current config
        config_res = supabase.table("app_config").select("value").eq("key", "topics").execute()
        current_config = config_res.data[0]["value"] if config_res.data else {"allowed": [], "blocked": []}
        
        with st.form("edit_topics"):
            allowed_str = st.text_area("Allowed Topics (Keywords for Relevance)", value=", ".join(current_config.get("allowed", [])))
            blocked_str = st.text_area("Blocked Topics (Exclude entirely)", value=", ".join(current_config.get("blocked", [])))
            priority_str = st.text_area("🚀 Priority Topics (Boost score by +1.5)", value=", ".join(current_config.get("priority", [])))
            
            if st.form_submit_button("Save Changes"):
                new_allowed = [t.strip() for t in allowed_str.split(",") if t.strip()]
                new_blocked = [t.strip() for t in blocked_str.split(",") if t.strip()]
                new_priority = [t.strip() for t in priority_str.split(",") if t.strip()]
                
                supabase.table("app_config").upsert({
                    "key": "topics",
                    "value": {
                        "allowed": new_allowed, 
                        "blocked": new_blocked,
                        "priority": new_priority
                    }
                }).execute()
                st.success("Configuration updated / Boosting active!")
                st.rerun()

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.caption("TechPulse AI v1.5")
