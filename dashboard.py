"""
🇲🇾 Bursa Malaysia IPO Alpha Screener — Streamlit Dashboard

Phase 3: Monetizable web dashboard with:
  - Overview (KPI cards, verdict distribution, top picks)
  - IPO List (filterable table, score breakdown, peer comparison)
  - Sector Analysis (sector heatmap, average scores)
  - New Scan (trigger analysis from scraped IPOs)

Deploy: streamlit run dashboard.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Path setup ──────────────────────────────────────────────────────────────
BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SCORES_DB = BOT_DIR / "ipo_scores.json"

sys.path.insert(0, str(BOT_DIR))

from scoring_engine import calculate_alpha_score, assess_liquidity_risk
from peer_comparison import compare_ipo_to_sector, full_pipeline_with_peers


# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bursa IPO Alpha Screener",
    page_icon="🇲🇾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colors ──────────────────────────────────────────────────────────────────
BURSA_BLUE = "#003B6F"
BURSA_GOLD = "#C8A951"
VERDICT_BUY = "#27AE60"
VERDICT_NEUTRAL = "#F39C12"
VERDICT_AVOID = "#E74C3C"
LIGHT_BG = "#F8F9FA"

VERDICT_COLORS = {
    "BUY": VERDICT_BUY,
    "NEUTRAL": VERDICT_NEUTRAL,
    "AVOID": VERDICT_AVOID,
}


# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<style>
    .main .block-container {{ padding-top: 1.5rem; }}
    h1, h2, h3 {{ color: {BURSA_BLUE} !important; }}
    .st-emotion-cache-1wmy9hl {{ background-color: {LIGHT_BG}; }}

    .kpi-card {{
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        text-align: center;
        border-left: 5px solid {BURSA_GOLD};
    }}
    .kpi-card .kpi-label {{
        font-size: 0.8rem;
        color: #7F8C8D;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .kpi-card .kpi-value {{
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0.3rem 0;
    }}
    .kpi-card .kpi-sub {{
        font-size: 0.75rem;
        color: #95A5A6;
    }}

    .verdict-buy {{ color: {VERDICT_BUY}; font-weight: 700; }}
    .verdict-neutral {{ color: {VERDICT_NEUTRAL}; font-weight: 700; }}
    .verdict-avoid {{ color: {VERDICT_AVOID}; font-weight: 700; }}

    .score-gauge-container {{ display: flex; justify-content: center; margin: 1rem 0; }}

    .footer {{
        text-align: center;
        color: #95A5A6;
        font-size: 0.75rem;
        padding: 2rem 0 0.5rem 0;
        border-top: 1px solid #ECF0F1;
        margin-top: 3rem;
    }}
</style>
""",
    unsafe_allow_html=True,
)


# ── Data helpers ────────────────────────────────────────────────────────────

def load_scores() -> list[dict]:
    """Load all scored IPOs from JSON storage."""
    if SCORES_DB.exists():
        try:
            return json.loads(SCORES_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_scores(scores: list[dict]):
    """Persist scored IPOs to JSON."""
    SCORES_DB.write_text(json.dumps(scores, indent=2, default=str))


def prepare_df(scores: list[dict]) -> pd.DataFrame:
    """Convert IPO score dicts to a flat DataFrame for display."""
    rows = []
    for s in scores:
        row = {
            "Company": s.get("company_name", "Unknown"),
            "Market": s.get("market", "N/A"),
            "Sector": s.get("sector", "N/A"),
            "Offer Price": s.get("offer_price", 0),
            "Market Cap (RM)": s.get("market_cap", 0),
            "P/E": s.get("pe_ratio", None),
            "Sector Avg P/E": s.get("sector_avg_pe", None),
            "Oversub (x)": s.get("oversubscription_rate", None),
            "Net Margin %": s.get("net_profit_margin", None),
            "Rev CAGR %": s.get("revenue_cagr_3yr", None),
            "Shariah": s.get("shariah_compliant", None),
            "Public Float %": s.get("public_float_pct", 0),
            "Alpha Score": s.get("alpha_score", 0),
            "Verdict": s.get("verdict", "N/A"),
            "Status": s.get("application_status", "N/A"),
            "Listing Date": s.get("listing_date", "N/A"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Alpha Score", ascending=False).reset_index(drop=True)
    return df


# ── Components ──────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, sub: str = "", color: str = BURSA_GOLD):
    """Render a KPI metric card."""
    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color: {color};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_gauge(score: float) -> go.Figure:
    """Create a Plotly gauge chart for the alpha score."""
    if score >= 70:
        color = VERDICT_BUY
        verdict = "BUY"
    elif score >= 50:
        color = VERDICT_NEUTRAL
        verdict = "NEUTRAL"
    else:
        color = VERDICT_AVOID
        verdict = "AVOID"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "/100", "font": {"size": 24, "color": color, "family": "Arial Black"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "darkgray"},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "lightgray",
            "steps": [
                {"range": [0, 50], "color": "#FFE5E5"},
                {"range": [50, 70], "color": "#FFF5D6"},
                {"range": [70, 100], "color": "#E5F9E7"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 2},
                "thickness": 0.6,
                "value": score,
            },
        },
        title={"text": verdict, "font": {"size": 18, "color": color, "family": "Arial Black"}},
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white",
        font={"color": BURSA_BLUE, "family": "Arial"},
    )
    return fig


def score_breakdown_chart(breakdown: dict) -> go.Figure:
    """Horizontal bar chart of per-criteria scores."""
    names = list(breakdown.keys())
    scores = [b.get("score", 0) for b in breakdown.values()]
    max_scores = [15, 15, 15, 15, 10, 15, 10]

    colors = [VERDICT_BUY if s >= m * 0.7 else VERDICT_NEUTRAL if s >= m * 0.4 else VERDICT_AVOID
              for s, m in zip(scores, max_scores)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names,
        x=scores,
        orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}/{m}" for s, m in zip(scores, max_scores)],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig.update_layout(
        title="Score Breakdown by Criteria",
        xaxis=dict(title="Score", range=[0, 18], showgrid=True, gridcolor="#ECF0F1"),
        yaxis=dict(title="", autorange="reversed"),
        height=280,
        margin=dict(l=10, r=40, t=30, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=BURSA_BLUE, size=11),
    )
    return fig


def verdict_distribution(scores: list[dict]) -> go.Figure:
    """Pie chart of verdict distribution."""
    counts = {"BUY": 0, "NEUTRAL": 0, "AVOID": 0}
    for s in scores:
        v = s.get("verdict", "N/A")
        if v in counts:
            counts[v] += 1

    labels = [k for k, v in counts.items() if v > 0]
    values = [v for v in counts.values() if v > 0]
    colors_pie = [VERDICT_COLORS.get(l, "#95A5A6") for l in labels]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors_pie, line=dict(color="white", width=2)),
        textinfo="label+percent",
        textfont=dict(size=13, color="white"),
        hole=0.45,
    )])
    fig.update_layout(
        title="Verdict Distribution",
        height=300,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="white",
        font=dict(color=BURSA_BLUE, size=12),
        showlegend=False,
    )
    return fig


def sector_score_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of average alpha score by sector."""
    if df.empty or "Sector" not in df.columns:
        return go.Figure()

    sector_avg = df.groupby("Sector")["Alpha Score"].mean().reset_index()
    sector_avg = sector_avg.sort_values("Alpha Score", ascending=True)

    colors_bar = [VERDICT_BUY if s >= 70 else VERDICT_NEUTRAL if s >= 50 else VERDICT_AVOID
                  for s in sector_avg["Alpha Score"]]

    fig = go.Figure(data=[go.Bar(
        y=sector_avg["Sector"],
        x=sector_avg["Alpha Score"],
        orientation="h",
        marker_color=colors_bar,
        text=sector_avg["Alpha Score"].round(1),
        textposition="outside",
        textfont=dict(size=10),
    )])
    fig.update_layout(
        title="Average Alpha Score by Sector",
        xaxis=dict(title="Avg Alpha Score", range=[0, 100], showgrid=True, gridcolor="#ECF0F1"),
        yaxis=dict(title="", autorange="reversed"),
        height=400,
        margin=dict(l=10, r=40, t=30, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=BURSA_BLUE, size=11),
    )
    return fig


def render_ipo_detail(scores: list[dict], idx: int):
    """Render full detail view for a selected IPO."""
    ipo = scores[idx]
    st.subheader(f"📋 {ipo.get('company_name', 'Unknown')}")

    # Gauge + quick stats
    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        gauge = score_gauge(ipo.get("alpha_score", 0))
        st.plotly_chart(gauge, use_container_width=True)

    with col2:
        st.markdown(f"**Market:** {ipo.get('market', 'N/A')}")
        st.markdown(f"**Sector:** {ipo.get('sector', 'N/A')}")
        st.markdown(f"**Offer Price:** RM{ipo.get('offer_price', 0):.2f}")
        st.markdown(f"**Market Cap:** RM{ipo.get('market_cap', 0):,.0f}")
        st.markdown(f"**P/E:** {ipo.get('pe_ratio', 'N/A')}")
        st.markdown(f"**Shariah:** {'✅ Yes' if ipo.get('shariah_compliant') else '❌ No' if ipo.get('shariah_compliant') is False else '❓ Unknown'}")

    with col3:
        st.markdown(f"**Oversub:** {ipo.get('oversubscription_rate', 'N/A')}x")
        st.markdown(f"**Net Margin:** {ipo.get('net_profit_margin', 'N/A')}%")
        st.markdown(f"**Rev CAGR:** {ipo.get('revenue_cagr_3yr', 'N/A')}%")
        st.markdown(f"**Public Float:** {ipo.get('public_float_pct', 0)}%")
        st.markdown(f"**Total Shares:** {ipo.get('total_shares', 0):,}")
        st.markdown(f"**Status:** {ipo.get('application_status', 'N/A')}")

    # Score breakdown chart
    breakdown = ipo.get("score_breakdown", {})
    if breakdown:
        st.plotly_chart(score_breakdown_chart(breakdown), use_container_width=True)

    # Peer comparison
    st.markdown("---")
    st.subheader("📊 Peer Comparison")
    try:
        peer_result = compare_ipo_to_sector(ipo)
        col_p1, col_p2 = st.columns([1, 1])

        with col_p1:
            pe_discount = peer_result['comparison']['pe_discount_pct']
            pe_status = "Discount" if pe_discount > 0 else ("Premium" if pe_discount < 0 else "In line")
            peers_df = pd.DataFrame([{
                "Metric": "P/E Ratio",
                "IPO": f"{peer_result['ipo_values']['pe_ratio']:.1f}x" if peer_result['ipo_values']['pe_ratio'] else "N/A",
                "Sector Avg": f"{peer_result['peer_sector_avg']['pe_ratio']:.1f}x",
                "Status": pe_status
            }, {
                "Metric": "Net Margin",
                "IPO": f"{peer_result['ipo_values']['net_margin_pct']:.1f}%" if peer_result['ipo_values']['net_margin_pct'] else "N/A",
                "Sector Avg": f"{peer_result['peer_sector_avg']['net_margin_pct']:.1f}%",
                "Status": peer_result['comparison']['margin_comparison']
            }, {
                "Metric": "Revenue Growth",
                "IPO": f"{peer_result['ipo_values']['revenue_cagr_pct']:.1f}%" if peer_result['ipo_values']['revenue_cagr_pct'] else "N/A",
                "Sector Avg": f"{peer_result['peer_sector_avg']['revenue_growth_pct']:.1f}%",
                "Status": peer_result['comparison']['growth_comparison']
            }])
            st.dataframe(peers_df, hide_index=True, use_container_width=True)

        with col_p2:
            st.markdown(f"**Peer Comparison Score:** {peer_result['comparison']['overall_score']:.0f}/100")
            st.markdown(f"**Valuation:** {peer_result['valuation_summary']}")
            st.markdown(f"**Sector Peers:** {', '.join(peer_result['top_sector_peers'][:4])}")
            st.markdown("")
            if peer_result.get("peer_insights"):
                for insight in peer_result["peer_insights"]:
                    st.markdown(f"💡 {insight}")

    except Exception as e:
        st.warning(f"Peer comparison unavailable: {e}")

    # Liquidity risk
    st.markdown("---")
    st.subheader("💧 Liquidity Risk Assessment")
    try:
        risk = assess_liquidity_risk(
            ipo.get("market", "N/A"),
            ipo.get("market_cap", 0),
            ipo.get("public_float_pct", 0),
        )
        risk_color = VERDICT_AVOID if risk["risk_level"] == "HIGH" else VERDICT_NEUTRAL if risk["risk_level"] == "MODERATE" else VERDICT_BUY
        st.markdown(f"**Risk Level:** <span style='color:{risk_color};font-weight:700;'>{risk['risk_level']}</span>", unsafe_allow_html=True)
        st.markdown(f"**Public Float (RM):** RM{risk['public_float_rm']:,.0f}")
        st.markdown(f"**Est. Volatility:** {risk['estimated_volatility_range']}")
        st.info(risk["warning"])
    except Exception as e:
        st.warning(f"Liquidity assessment unavailable: {e}")


def render_new_scan():
    """Form to trigger a new IPO scan and analysis."""
    st.subheader("🆕 New IPO Scan")

    st.markdown("""
    Enter IPO details manually to run the scoring engine.
    Data will be saved to the IPO database and appear in the dashboard.
    """)

    with st.form("new_ipo_form"):
        col1, col2 = st.columns(2)

        with col1:
            company = st.text_input("Company Name", placeholder="e.g. Alpha Tech Bhd")
            market = st.selectbox("Market", ["ACE", "Main", "LEAP"])
            sector = st.selectbox("Sector", [
                "Technology", "Industrial / Industrial Products", "Property / Property Development",
                "Healthcare", "Consumer / Consumer Products", "Construction",
                "Energy / Oil & Gas", "Plantation", "Financial Services",
                "REIT", "Telecommunications", "Transportation & Logistics",
            ])
            offer_price = st.number_input("Offer Price (RM)", min_value=0.01, step=0.05, format="%.2f")
            market_cap = st.number_input("Market Cap (RM)", min_value=0.0, step=1_000_000.0, format="%.0f")
            pe_ratio = st.number_input("P/E Ratio", min_value=0.0, step=0.1, format="%.1f")
            sector_avg_pe = st.number_input("Sector Avg P/E", min_value=0.0, step=0.1, format="%.1f")
            oversub = st.number_input("Oversubscription Rate (x)", min_value=0.0, step=0.1, format="%.1f")

        with col2:
            net_margin = st.number_input("Net Profit Margin %", min_value=-50.0, step=0.5, format="%.1f")
            rev_cagr = st.number_input("Revenue CAGR (3yr) %", min_value=-50.0, step=0.5, format="%.1f")
            shariah = st.selectbox("Shariah Compliant", ["Yes", "No", "Unknown"])
            float_pct = st.slider("Public Float %", 0, 100, 25)
            total_shares = st.number_input("Total Shares", min_value=1, step=1_000_000, format="%d")
            moratorium = st.number_input("Moratorium Period (years)", min_value=0.0, step=0.5, format="%.1f")
            promoter_pct = st.number_input("Promoter Ownership %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f")
            status = st.selectbox("Application Status", ["Open", "Closing", "Listed", "Pending"])

        submitted = st.form_submit_button("📊 Score & Save", type="primary", use_container_width=True)

        if submitted:
            ipo_data = {
                "company_name": company,
                "market": market,
                "sector": sector,
                "offer_price": offer_price,
                "market_cap": market_cap,
                "pe_ratio": pe_ratio or None,
                "sector_avg_pe": sector_avg_pe or None,
                "oversubscription_rate": oversub or None,
                "proceeds_utilization": {"capex_pct": None, "debt_pct": None, "working_capital_pct": None},
                "net_profit_margin": net_margin or None,
                "revenue_cagr_3yr": rev_cagr or None,
                "shariah_compliant": True if shariah == "Yes" else False if shariah == "No" else None,
                "moratorium_period_years": moratorium or None,
                "promoter_ownership_pct": promoter_pct or None,
                "total_shares": total_shares,
                "public_float_pct": float_pct,
                "application_status": status,
                "listing_date": None,
            }

            result = calculate_alpha_score(ipo_data)

            ipo_data["alpha_score"] = result["total_score"]
            ipo_data["verdict"] = result["verdict"]
            ipo_data["score_breakdown"] = result["breakdown"]

            scores = load_scores()
            # Check for duplicate by company name
            existing_names = {s.get("company_name", "").lower().strip() for s in scores}
            if company.lower().strip() in existing_names:
                st.error(f"⚠️ {company} is already in the database! Edit the existing entry instead.")
            else:
                scores.append(ipo_data)
                save_scores(scores)
                st.success(f"✅ {company} scored! Alpha: {result['total_score']:.1f}/100 → **{result['verdict']}**")
                st.balloons()


# ── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.markdown(
    f"""
    <div style="text-align:center; padding: 0.5rem 0;">
        <h1 style="font-size:1.5rem; margin:0;">🇲🇾 Bursa IPO</h1>
        <p style="color:{BURSA_GOLD}; font-weight:600; margin:0;">Alpha Screener</p>
        <hr style="margin:1rem 0; border-color:#ECF0F1;">
    </div>
    """,
    unsafe_allow_html=True,
)

scores = load_scores()
df = prepare_df(scores)

# Sidebar stats
st.sidebar.markdown("### 📊 Database")
st.sidebar.metric("Total IPOs", len(scores))
if not df.empty:
    buy_count = len(df[df["Verdict"] == "BUY"])
    neutral_count = len(df[df["Verdict"] == "NEUTRAL"])
    avoid_count = len(df[df["Verdict"] == "AVOID"])
    avg_score = df["Alpha Score"].mean()
    st.sidebar.metric("BUY Signals", buy_count)
    st.sidebar.metric("NEUTRAL", neutral_count)
    st.sidebar.metric("AVOID", avoid_count)
    st.sidebar.metric("Avg Alpha Score", f"{avg_score:.1f}")

# Navigation
st.sidebar.markdown("### 🧭 Navigation")
page = st.sidebar.radio(
    "Go to",
    ["📈 Overview", "📋 IPO List", "🏭 Sector Analysis", "🆕 New Scan"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    f'<div style="text-align:center;font-size:0.75rem;color:#95A5A6;">'
    f'v1.0.0 · {datetime.now().strftime("%b %Y")}</div>',
    unsafe_allow_html=True,
)


# ── Pages ───────────────────────────────────────────────────────────────────

if page == "📈 Overview":
    st.title("🇲🇾 Bursa Malaysia IPO Alpha Screener")
    st.markdown("*Automated pre-listing valuation and scoring for Malaysian IPOs*")

    if not scores:
        st.info("📭 No IPOs scored yet. Add one via **🆕 New Scan** or import data.")
    else:
        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            kpi_card("Total IPOs", str(len(scores)), f"Database total")
        with k2:
            kpi_card("BUY Signals", str(buy_count), f"{buy_count / len(scores) * 100:.0f}% of total", VERDICT_BUY)
        with k3:
            kpi_card("NEUTRAL", str(neutral_count), f"{neutral_count / len(scores) * 100:.0f}% of total", VERDICT_NEUTRAL)
        with k4:
            kpi_card("AVOID", str(avoid_count), f"{avoid_count / len(scores) * 100:.0f}% of total", VERDICT_AVOID)
        with k5:
            kpi_card("Avg Score", f"{avg_score:.1f}", "across all IPOs", BURSA_BLUE)

        st.markdown("---")

        # Verdict distribution + top picks
        col_a, col_b = st.columns([1, 1.5])

        with col_a:
            fig_pie = verdict_distribution(scores)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_b:
            st.subheader("🏆 Top 3 Picks (Highest Alpha)")
            top3 = df.head(3)
            for _, row in top3.iterrows():
                color = VERDICT_COLORS.get(row["Verdict"], "#95A5A6")
                st.markdown(
                    f"""
                    <div style="background:white; border-radius:8px; padding:0.6rem 1rem; margin:0.3rem 0;
                                border-left:4px solid {color}; box-shadow:0 1px 4px rgba(0,0,0,0.04);">
                        <b>{row['Company']}</b> <span style="color:{color};font-weight:700;">[{row['Verdict']}]</span>
                        <span style="float:right;font-weight:700;">{row['Alpha Score']:.0f}/100</span><br>
                        <span style="font-size:0.8rem;color:#7F8C8D;">
                            {row['Sector']} · {row['Market']} · RM{row['Offer Price']:.2f}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # Sector overview
        if not df.empty and "Sector" in df.columns:
            fig_sector = sector_score_chart(df)
            st.plotly_chart(fig_sector, use_container_width=True)

        # Recent additions
        st.markdown("---")
        st.subheader("📜 Recently Added")
        recent = df.head(10)[["Company", "Market", "Sector", "Alpha Score", "Verdict"]]
        st.dataframe(recent, hide_index=True, use_container_width=True)


elif page == "📋 IPO List":
    st.title("📋 IPO Database")

    if not scores:
        st.info("📭 No IPOs in database. Add one via **🆕 New Scan**.")
    else:
        # Filters
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            verdict_filter = st.multiselect("Verdict", ["BUY", "NEUTRAL", "AVOID"], default=["BUY", "NEUTRAL", "AVOID"])
        with col_f2:
            sectors = sorted(df["Sector"].unique())
            sector_filter = st.multiselect("Sector", sectors, default=sectors)
        with col_f3:
            markets = sorted(df["Market"].unique())
            market_filter = st.multiselect("Market", markets, default=markets)
        with col_f4:
            search = st.text_input("🔍 Search Company", placeholder="Type name...")

        # Apply filters
        filtered = df.copy()
        if verdict_filter:
            filtered = filtered[filtered["Verdict"].isin(verdict_filter)]
        if sector_filter:
            filtered = filtered[filtered["Sector"].isin(sector_filter)]
        if market_filter:
            filtered = filtered[filtered["Market"].isin(market_filter)]
        if search:
            filtered = filtered[filtered["Company"].str.contains(search, case=False, na=False)]

        st.caption(f"Showing {len(filtered)} of {len(df)} IPOs")

        # Display as clickable cards
        for idx, row in filtered.iterrows():
            color = VERDICT_COLORS.get(row["Verdict"], "#95A5A6")
            with st.expander(f"🏷️ {row['Company']} — [ {row['Verdict']} ]  Score: {row['Alpha Score']:.0f}/100"):
                # Find the actual index in the original scores list
                original_idx = None
                for i, s in enumerate(scores):
                    if s.get("company_name") == row["Company"]:
                        original_idx = i
                        break
                if original_idx is not None:
                    render_ipo_detail(scores, original_idx)


elif page == "🏭 Sector Analysis":
    st.title("🏭 Sector Analysis")

    if not scores:
        st.info("📭 No IPOs in database yet.")
    else:
        col_s1, col_s2 = st.columns([1, 1])

        with col_s1:
            fig_sector = sector_score_chart(df)
            st.plotly_chart(fig_sector, use_container_width=True)

        with col_s2:
            st.subheader("Sector Snapshot")
            if not df.empty:
                sector_stats = df.groupby("Sector").agg(
                    Count=("Company", "count"),
                    Avg_Score=("Alpha Score", "mean"),
                    BUY=("Verdict", lambda x: (x == "BUY").sum()),
                    NEUTRAL=("Verdict", lambda x: (x == "NEUTRAL").sum()),
                    AVOID=("Verdict", lambda x: (x == "AVOID").sum()),
                ).reset_index().sort_values("Avg_Score", ascending=False)
                sector_stats.columns = ["Sector", "Count", "Avg Score", "BUY", "NEUTRAL", "AVOID"]
                st.dataframe(sector_stats, hide_index=True, use_container_width=True)

        st.markdown("---")

        # Score distribution by sector
        st.subheader("Score Distribution by Sector")
        fig_box = px.box(
            df, x="Sector", y="Alpha Score",
            color="Sector",
            color_discrete_sequence=px.colors.qualitative.Set2,
            points="all",
        )
        fig_box.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(color=BURSA_BLUE),
            showlegend=False,
            xaxis_title="",
        )
        st.plotly_chart(fig_box, use_container_width=True)

        # Market breakdown
        st.markdown("---")
        st.subheader("Market Breakdown")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            market_count = df["Market"].value_counts().reset_index()
            market_count.columns = ["Market", "Count"]
            fig_market = px.bar(
                market_count, x="Market", y="Count",
                color="Market",
                color_discrete_sequence=[BURSA_BLUE, BURSA_GOLD, "#7F8C8D"],
                text="Count",
            )
            fig_market.update_layout(
                height=250, showlegend=False,
                paper_bgcolor="white", plot_bgcolor="white",
                font=dict(color=BURSA_BLUE),
            )
            st.plotly_chart(fig_market, use_container_width=True)

        with col_m2:
            market_avg = df.groupby("Market")["Alpha Score"].mean().reset_index()
            market_avg.columns = ["Market", "Avg Alpha Score"]
            st.dataframe(market_avg, hide_index=True, use_container_width=True)


elif page == "🆕 New Scan":
    st.title("🆕 New IPO Scan")
    render_new_scan()


# ── Footer ──────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="footer">
        Bursa IPO Alpha Screener · AI-powered analysis · Not financial advice<br>
        Data sourced from Bursa Malaysia, KLSE Screener & IPOWatch<br>
        v1.0.0 | Built with Streamlit + Plotly
    </div>
    """,
    unsafe_allow_html=True,
)
