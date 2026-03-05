
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pytrends.request import TrendReq
import time
import numpy as np

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Global Crisis Search Monitor",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .stApp { background: #0a0e1a; color: #e2e8f0; }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid #334155;
  }
  section[data-testid="stSidebar"] * { color: #94a3b8 !important; }
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 { color: #f1f5f9 !important; }

  /* Metric cards */
  .metric-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 8px;
    transition: transform .2s, box-shadow .2s;
  }
  .metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,.4); }

  .metric-value { font-size: 2.2rem; font-weight: 700; color: #f8fafc; line-height: 1; }
  .metric-label { font-size: .8rem; color: #64748b; text-transform: uppercase; letter-spacing: .08em; margin-top: 4px; }
  .metric-delta { font-size: .85rem; margin-top: 6px; }
  .delta-up   { color: #ef4444; }
  .delta-down { color: #22c55e; }

  /* Score badge */
  .score-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 600;
  }

  /* Section headers */
  .section-header {
    font-size: 1.15rem;
    font-weight: 600;
    color: #f1f5f9;
    border-left: 3px solid #6366f1;
    padding-left: 12px;
    margin: 24px 0 12px;
  }

  /* Table */
  .stDataFrame { border-radius: 10px; overflow: hidden; }
  .stDataFrame thead th { background: #1e293b !important; color: #94a3b8 !important; }

  /* Status pills */
  .pill-critical { background:#7f1d1d; color:#fca5a5; border-radius:999px; padding:2px 10px; font-size:.75rem; font-weight:600; }
  .pill-high     { background:#7c2d12; color:#fdba74; border-radius:999px; padding:2px 10px; font-size:.75rem; font-weight:600; }
  .pill-moderate { background:#713f12; color:#fde68a; border-radius:999px; padding:2px 10px; font-size:.75rem; font-weight:600; }
  .pill-low      { background:#14532d; color:#86efac; border-radius:999px; padding:2px 10px; font-size:.75rem; font-weight:600; }

  /* Hide default streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
KEYWORDS = ["war", "leave country", "inflation crisis", "bank collapse", "food shortage"]

COUNTRIES = {
    "United States": "US",
    "India":         "IN",
    "Germany":       "DE",
    "Pakistan":      "PK",
    "Argentina":     "AR",
    "South Africa":  "ZA",
    "United Kingdom":"GB",
    "Turkey":        "TR",
    "Brazil":        "BR",
    "Indonesia":     "ID",
}

ISO3_MAP = {
    "United States":  "USA",
    "India":          "IND",
    "Germany":        "DEU",
    "Pakistan":       "PAK",
    "Argentina":      "ARG",
    "South Africa":   "ZAF",
    "United Kingdom": "GBR",
    "Turkey":         "TUR",
    "Brazil":         "BRA",
    "Indonesia":      "IDN",
}

KEYWORD_WEIGHTS = {
    "war":             0.25,
    "leave country":   0.20,
    "inflation crisis":0.20,
    "bank collapse":   0.20,
    "food shortage":   0.15,
}

TIMEFRAMES = {
    "Past 7 days":   "now 7-d",
    "Past 30 days":  "today 1-m",
    "Past 90 days":  "today 3-m",
    "Past 12 months":"today 12-m",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def score_to_level(score):
    if score >= 70:   return "CRITICAL", "#ef4444"
    if score >= 50:   return "HIGH",     "#f97316"
    if score >= 30:   return "MODERATE", "#eab308"
    return "LOW", "#22c55e"

def score_to_pill(score):
    lvl, _ = score_to_level(score)
    css = lvl.lower()
    return f'<span class="pill-{css}">{lvl}</span>'

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trends(timeframe: str) -> pd.DataFrame:
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25), retries=3, backoff_factor=0.5)
    records = {c: {} for c in COUNTRIES}

    for kw in KEYWORDS:
        try:
            pytrends.build_payload([kw], timeframe=timeframe, geo="")
            df = pytrends.interest_by_region(resolution="COUNTRY", inc_low_vol=True, inc_geo_code=False)
            for country, code in COUNTRIES.items():
                # Map display name → country name used by pytrends
                # pytrends uses English country names as index
                _map = {
                    "United States":  "United States",
                    "India":          "India",
                    "Germany":        "Germany",
                    "Pakistan":       "Pakistan",
                    "Argentina":      "Argentina",
                    "South Africa":   "South Africa",
                    "United Kingdom": "United Kingdom",
                    "Turkey":         "Turkey",
                    "Brazil":         "Brazil",
                    "Indonesia":      "Indonesia",
                }
                idx = _map.get(country, country)
                val = int(df.loc[idx, kw]) if idx in df.index and kw in df.columns else 0
                records[country][kw] = val
            time.sleep(0.8)
        except Exception as e:
            for country in COUNTRIES:
                records[country][kw] = 0

    rows = []
    for country, kw_vals in records.items():
        score = sum(kw_vals.get(kw, 0) * KEYWORD_WEIGHTS[kw] for kw in KEYWORDS)
        rows.append({"Country": country, **kw_vals, "Crisis Score": round(score, 1)})

    return pd.DataFrame(rows).sort_values("Crisis Score", ascending=False).reset_index(drop=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌍 Crisis Monitor")
    st.markdown("---")

    timeframe_label = st.selectbox("📅 Timeframe", list(TIMEFRAMES.keys()), index=1)
    timeframe = TIMEFRAMES[timeframe_label]

    st.markdown("---")
    st.markdown("### 🔑 Keywords")
    for kw, w in KEYWORD_WEIGHTS.items():
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:5px 0;'>"
            f"<span style='color:#cbd5e1;font-size:.85rem;'>{kw}</span>"
            f"<span style='color:#6366f1;font-weight:600;font-size:.85rem;'>{int(w*100)}%</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 🌐 Countries")
    for c in COUNTRIES:
        st.markdown(f"<span style='color:#94a3b8;font-size:.82rem;'>• {c}</span>", unsafe_allow_html=True)

    st.markdown("---")
    refresh = st.button("🔄 Refresh Data", use_container_width=True)
    if refresh:
        st.cache_data.clear()

    st.markdown(
        "<p style='color:#475569;font-size:.72rem;margin-top:24px;'>Data: Google Trends via pytrends<br>Scores updated hourly</p>",
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:28px 0 10px;">
  <h1 style="color:#f8fafc;font-size:2.2rem;font-weight:700;margin:0;">
    🌍 Global Crisis Search Monitor
  </h1>
  <p style="color:#64748b;font-size:1rem;margin-top:6px;">
    Real-time crisis attention scores powered by Google Trends search behaviour
  </p>
</div>
""", unsafe_allow_html=True)

# ── Fetch Data ────────────────────────────────────────────────────────────────
with st.spinner("⏳ Fetching live Google Trends data…"):
    df = fetch_trends(timeframe)

df["ISO3"]  = df["Country"].map(ISO3_MAP)
df["Level"] = df["Crisis Score"].apply(lambda s: score_to_level(s)[0])
df["Color"] = df["Crisis Score"].apply(lambda s: score_to_level(s)[1])
df["Rank"]  = range(1, len(df) + 1)

top    = df.iloc[0]
avg    = df["Crisis Score"].mean()
n_crit = (df["Crisis Score"] >= 70).sum()
n_high = (df["Crisis Score"] >= 50).sum()

# ── KPI Strip ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Key Indicators</div>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

def kpi(col, icon, label, value, sub="", sub_cls="delta-down"):
    col.markdown(
        f"""<div class="metric-card">
              <div class="metric-label">{icon} {label}</div>
              <div class="metric-value">{value}</div>
              <div class="metric-delta {sub_cls}">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )

kpi(k1, "🏆", "Highest Crisis Score", f"{top['Crisis Score']:.0f}", top["Country"], "delta-up")
kpi(k2, "📈", "Global Average Score",  f"{avg:.1f}", f"Across {len(df)} countries")
kpi(k3, "🔴", "Countries at High+",    str(n_high),  f"{n_crit} CRITICAL", "delta-up" if n_crit else "delta-down")
kpi(k4, "🕒", "Timeframe",             timeframe_label, "Google Trends")

# ── World Map ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🗺️ Crisis Attention World Map</div>', unsafe_allow_html=True)

fig_map = go.Figure(go.Choropleth(
    locations=df["ISO3"],
    z=df["Crisis Score"],
    text=df["Country"],
    customdata=np.stack([df["Country"], df["Crisis Score"], df["Level"]], axis=-1),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Crisis Score: <b>%{customdata[1]:.1f}</b><br>"
        "Level: <b>%{customdata[2]}</b><extra></extra>"
    ),
    colorscale=[
        [0.0,  "#0f172a"],
        [0.25, "#1e3a5f"],
        [0.5,  "#7c3aed"],
        [0.75, "#dc2626"],
        [1.0,  "#fef08a"],
    ],
    zmin=0, zmax=100,
    marker_line_color="#334155",
    marker_line_width=0.5,
    colorbar=dict(
        title=dict(text="Crisis Score", font=dict(color="#94a3b8", size=12)),
        tickfont=dict(color="#94a3b8"),
        bgcolor="#0f172a",
        bordercolor="#334155",
        borderwidth=1,
        thickness=14,
        len=0.7,
    ),
))

fig_map.update_layout(
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#0a0e1a",
    geo=dict(
        bgcolor="#0a0e1a",
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#334155",
        showland=True,
        landcolor="#1e293b",
        showocean=True,
        oceancolor="#0a0e1a",
        showlakes=False,
        showcountries=True,
        countrycolor="#334155",
        projection_type="natural earth",
    ),
    margin=dict(l=0, r=0, t=10, b=0),
    height=460,
)

st.plotly_chart(fig_map, use_container_width=True)

# ── Bar + Radar side-by-side ──────────────────────────────────────────────────
st.markdown('<div class="section-header">📉 Country Rankings & Keyword Breakdown</div>', unsafe_allow_html=True)
col_bar, col_radar = st.columns([1.1, 0.9])

with col_bar:
    df_sorted = df.sort_values("Crisis Score")
    colors = df_sorted["Crisis Score"].apply(
        lambda s: "#ef4444" if s >= 70 else "#f97316" if s >= 50 else "#eab308" if s >= 30 else "#22c55e"
    )

    fig_bar = go.Figure(go.Bar(
        x=df_sorted["Crisis Score"],
        y=df_sorted["Country"],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=0),
            cornerradius=5,
        ),
        text=df_sorted["Crisis Score"].apply(lambda s: f"{s:.1f}"),
        textposition="outside",
        textfont=dict(color="#94a3b8", size=11),
        hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}<extra></extra>",
    ))

    fig_bar.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        xaxis=dict(
            range=[0, 110],
            gridcolor="#1e293b",
            tickfont=dict(color="#475569"),
            title=dict(text="Crisis Attention Score", font=dict(color="#64748b", size=11)),
            zeroline=False,
        ),
        yaxis=dict(tickfont=dict(color="#cbd5e1", size=11), gridcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=50, t=10, b=40),
        height=400,
        hoverlabel=dict(bgcolor="#1e293b", font_color="#f1f5f9"),
        bargap=0.22,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_radar:
    top5 = df.head(5)
    categories = KEYWORDS + [KEYWORDS[0]]

    fig_rad = go.Figure()
    palette = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6"]
    for i, row in top5.iterrows():
        vals = [row[kw] for kw in KEYWORDS] + [row[KEYWORDS[0]]]
        fig_rad.add_trace(go.Scatterpolar(
            r=vals, theta=categories,
            fill="toself",
            name=row["Country"],
            line=dict(color=palette[i % 5], width=2),
            fillcolor=palette[i % 5].replace("#", "rgba(") + ",0.1)" if False else palette[i % 5],
            opacity=0.75,
        ))

    fig_rad.update_layout(
        polar=dict(
            bgcolor="#0f172a",
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(color="#475569", size=9), gridcolor="#1e293b", linecolor="#334155"),
            angularaxis=dict(tickfont=dict(color="#94a3b8", size=10), gridcolor="#1e293b", linecolor="#334155"),
        ),
        paper_bgcolor="#0f172a",
        legend=dict(font=dict(color="#94a3b8", size=10), bgcolor="rgba(0,0,0,0)", bordercolor="#334155"),
        margin=dict(l=30, r=30, t=20, b=20),
        height=400,
        hoverlabel=dict(bgcolor="#1e293b", font_color="#f1f5f9"),
        title=dict(text="Top 5 – Keyword Radar", font=dict(color="#64748b", size=12), x=0.5),
    )
    st.plotly_chart(fig_rad, use_container_width=True)

# ── Stacked Bar ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🔍 Keyword Contribution per Country</div>', unsafe_allow_html=True)

kw_colors = {"war":"#ef4444","leave country":"#f97316","inflation crisis":"#eab308","bank collapse":"#a855f7","food shortage":"#3b82f6"}
df_stack = df.sort_values("Crisis Score", ascending=False)

fig_stack = go.Figure()
for kw in KEYWORDS:
    fig_stack.add_trace(go.Bar(
        name=kw.title(),
        x=df_stack["Country"],
        y=df_stack[kw],
        marker_color=kw_colors[kw],
        hovertemplate=f"<b>%{{x}}</b><br>{kw}: %{{y}}<extra></extra>",
    ))

fig_stack.update_layout(
    barmode="stack",
    paper_bgcolor="#0f172a",
    plot_bgcolor="#0f172a",
    xaxis=dict(tickfont=dict(color="#cbd5e1", size=11), gridcolor="rgba(0,0,0,0)"),
    yaxis=dict(title="Search Interest (0-100)", tickfont=dict(color="#475569"), gridcolor="#1e293b", zeroline=False, title_font=dict(color="#64748b",size=11)),
    legend=dict(font=dict(color="#94a3b8", size=10), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=40, b=10),
    height=340,
    hoverlabel=dict(bgcolor="#1e293b", font_color="#f1f5f9"),
    bargap=0.18,
)
st.plotly_chart(fig_stack, use_container_width=True)

# ── Data Table ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Detailed Crisis Score Table</div>', unsafe_allow_html=True)

display_df = df[["Rank","Country","Crisis Score","Level"] + KEYWORDS].copy()
display_df.columns = ["#", "Country", "Score", "Level", "War", "Leave Country", "Inflation Crisis", "Bank Collapse", "Food Shortage"]

def color_score(val):
    if isinstance(val, (int, float)):
        if val >= 70:   return "background-color:#7f1d1d;color:#fca5a5;"
        if val >= 50:   return "background-color:#7c2d12;color:#fdba74;"
        if val >= 30:   return "background-color:#713f12;color:#fde68a;"
        return "background-color:#14532d;color:#86efac;"
    return ""

def color_level(val):
    m = {"CRITICAL":"background-color:#7f1d1d;color:#fca5a5;",
         "HIGH":     "background-color:#7c2d12;color:#fdba74;",
         "MODERATE": "background-color:#713f12;color:#fde68a;",
         "LOW":      "background-color:#14532d;color:#86efac;"}
    return m.get(val, "")

styled = (
    display_df.style
    .applymap(color_score, subset=["Score","War","Leave Country","Inflation Crisis","Bank Collapse","Food Shortage"])
    .applymap(color_level, subset=["Level"])
    .set_properties(**{"background-color":"#0f172a","color":"#e2e8f0","border-color":"#1e293b"})
    .set_table_styles([
        {"selector":"thead th", "props":[("background","#1e293b"),("color","#94a3b8"),("font-size","0.8rem"),("text-transform","uppercase"),("letter-spacing","0.05em")]},
        {"selector":"tbody tr:hover td", "props":[("background","#1e293b !important")]},
    ])
    .format({"Score":"{:.1f}"})
    .hide(axis="index")
)
st.dataframe(styled, use_container_width=True, height=420)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<hr style="border:1px solid #1e293b;margin:36px 0 16px;">
<p style="color:#334155;font-size:.78rem;text-align:center;">
  Global Crisis Search Monitor &nbsp;•&nbsp; Powered by Google Trends &amp; pytrends &nbsp;•&nbsp;
  Scores are weighted aggregates of search interest (0–100) &nbsp;•&nbsp; Data refreshes every hour
</p>
""", unsafe_allow_html=True)
