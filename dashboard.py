"""
Bursa Malaysia IPO Alpha Screener — Single-Page Dashboard
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from scoring_engine import calculate_alpha_score, assess_liquidity_risk
from report_generator import generate_report
from peer_comparison import compare_ipo_to_sector
from payment_gateway import create_checkout_session, verify_payment, check_stripe_config, get_publishable_key, DEFAULT_PRICE_RM

# --- Stripe / payment state ---
if 'payment_session' not in st.session_state:
    st.session_state.payment_session = None
if 'payment_ticker' not in st.session_state:
    st.session_state.payment_ticker = None
if 'payment_verified' not in st.session_state:
    st.session_state.payment_verified = {}
from report_generator import generate_ipo_report

BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SCORES_DB = BOT_DIR / "ipo_scores.json"

sys.path.insert(0, str(BOT_DIR))

st.set_page_config(
    page_title="Bursa IPO Alpha Screener",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

    .badge {{
        display: inline-block;
        border-radius: 6px;
        padding: 0.15rem 0.6rem;
        font-size: 0.85rem;
        font-weight: 700;
    }}

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


def load_scores() -> list[dict]:
    if SCORES_DB.exists():
        try:
            return json.loads(SCORES_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_scores(scores: list[dict]):
    SCORES_DB.write_text(json.dumps(scores, indent=2, default=str))


def prepare_df(scores: list[dict]) -> pd.DataFrame:
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
            "Alpha Score": s.get("alpha_score") or s.get("total_score", 0),
            "Verdict": s.get("verdict", "N/A"),
            "Status": s.get("application_status", "N/A"),
            "Listing Date": s.get("listing_date", "N/A"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Alpha Score", ascending=False).reset_index(drop=True)
    return df


def kpi_card(label: str, value: str, sub: str = "", color: str = BURSA_GOLD):
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


def render_ipo_detail(ipo: dict):
    score_val = ipo.get("alpha_score") or ipo.get("total_score", 0)
    breakdown = ipo.get("score_breakdown") or ipo.get("breakdown", {})
    quality = ipo.get("data_quality", "")

    st.subheader(f" {ipo.get('company_name', 'Unknown')}")

    if quality:
        q_color = {"HIGH": "#27AE60", "MEDIUM": "#F39C12", "LOW": "#E74C3C"}.get(quality, "#95A5A6")
        st.markdown(
            f"<div style='background:{q_color}15;border:1px solid {q_color};border-radius:6px;"
            f"padding:0.3rem 0.8rem;margin-bottom:0.5rem;display:inline-block;font-size:0.85rem;'>"
            f" <b>Data Quality:</b> <span style='color:{q_color};font-weight:700;'>{quality}</span></div>",
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        gauge = score_gauge(score_val)
        st.plotly_chart(gauge, width='stretch', key=ipo.get('company_name','unk') + '_gauge')

    with col2:
        st.markdown(f"**Market:** {ipo.get('market', 'N/A')}")
        st.markdown(f"**Sector:** {ipo.get('sector', 'N/A')}")
        st.markdown(f"**Offer Price:** RM{ipo.get('offer_price', 0):.2f}")
        st.markdown(f"**Market Cap:** RM{ipo.get('market_cap', 0):,.0f}")
        pe = ipo.get('pe_ratio') or 'N/A'
        st.markdown(f"**P/E:** {pe}")
        shariah = ipo.get('shariah_compliant')
        shariah_str = ' Yes' if shariah else (' No' if shariah is False else ' Unknown')
        st.markdown(f"**Shariah:** {shariah_str}")

    with col3:
        oversub = ipo.get('oversubscription_rate') or 'N/A'
        st.markdown(f"**Oversub:** {oversub}x")
        margin = ipo.get('net_profit_margin') or 'N/A'
        st.markdown(f"**Net Margin:** {margin}%")
        cagr = ipo.get('revenue_cagr_3yr') or 'N/A'
        st.markdown(f"**Rev CAGR:** {cagr}%")
        st.markdown(f"**Public Float:** {ipo.get('public_float_pct', 0)}%")
        st.markdown(f"**Total Shares:** {ipo.get('total_shares', 0):,}")
        st.markdown(f"**Status:** {ipo.get('application_status', 'N/A')}")

    if quality == "LOW":
        st.warning(" Limited data available — score is conservative. Add fundamental data for better accuracy.")
    elif quality == "MEDIUM":
        st.info(" Moderate data available — some scoring criteria use neutral defaults.")

    if breakdown:
        st.plotly_chart(score_breakdown_chart(breakdown), width='stretch', key=ipo.get('company_name','unk') + '_breakdown')

    st.markdown("---")
    st.subheader(" Peer Comparison")
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
            st.dataframe(peers_df, hide_index=True, width='stretch')

        with col_p2:
            st.markdown(f"**Peer Comparison Score:** {peer_result['comparison']['overall_score']:.0f}/100")
            st.markdown(f"**Valuation:** {peer_result['valuation_summary']}")
            st.markdown(f"**Sector Peers:** {', '.join(peer_result['top_sector_peers'][:4])}")
            st.markdown("")
            if peer_result.get("peer_insights"):
                for insight in peer_result["peer_insights"]:
                    st.markdown(f" {insight}")

    except Exception as e:
        st.warning(f"Peer comparison unavailable: {e}")

    st.markdown("---")
    st.subheader(" Liquidity Risk Assessment")
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


def render_card(ipo: dict, scores_list: list[dict]):
    score_val = ipo.get("alpha_score") or ipo.get("total_score", 0)
    verdict = ipo.get("verdict", "N/A")
    color = VERDICT_COLORS.get(verdict, "#95A5A6")

    company_name = ipo.get("company_name", "Unknown")
    ticker = ipo.get("ticker", "")

    shariah = ipo.get("shariah_compliant")
    shariah_badge = " ✅ Shariah" if shariah is True else (" ❌ Non-Shariah" if shariah is False else "")

    label_parts = [f" {company_name}"]
    if ticker:
        label_parts.append(f"[{ticker}]")
    label_parts.append(f" — {ipo.get('sector', 'N/A')}{shariah_badge}")
    label_parts.append(f"  |  Alpha: {score_val:.0f}/100")
    label_parts.append(f"  [{verdict}]")

    expander_label = "".join(label_parts)

    with st.expander(expander_label, expanded=False):
        shariah_color = "#27AE60" if shariah is True else ("#E74C3C" if shariah is False else "#95A5A6")
        shariah_label = "✅ Shariah" if shariah is True else ("❌ Non-Shariah" if shariah is False else "❓ Unknown")
        st.markdown(
            f"""
            <div style="display:flex; gap:0.5rem; align-items:center; margin-bottom:0.5rem;">
                <span class="badge" style="background:{color}15; border:1px solid {color}; color:{color};">
                    {score_val:.0f}/100
                </span>
                <span class="badge" style="background:{color}15; border:1px solid {color}; color:{color};">
                    {verdict}
                </span>
                <span class="badge" style="background:{shariah_color}15; border:1px solid {shariah_color}; color:{shariah_color};">
                    {shariah_label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        refresh_key = f"refresh_{company_name}_{ticker or 'no_ticker'}"
        if st.button(" Refresh Data", key=refresh_key, help="Re-score this IPO with current data", width='stretch'):
            result = calculate_alpha_score(ipo)
            ipo["alpha_score"] = result["total_score"]
            ipo["verdict"] = result["verdict"]
            ipo["score_breakdown"] = result["breakdown"]

            for i, s in enumerate(scores_list):
                if s.get("company_name") == company_name:
                    scores_list[i] = ipo
                    break
            save_scores(scores_list)
            st.success(f" {company_name} re-scored: {result['total_score']:.1f}/100 → {result['verdict']}")
            st.rerun()

        # --- Buy Report with Stripe payment ---
        report_key = f'report_{ipo.get("company_name", "")}_{ipo.get("ticker", "")}'
        ticker = ipo.get('ticker', '')
        company = ipo.get('company_name', '')
        
        # Check if already paid this session
        already_paid = st.session_state.payment_verified.get(ticker, False)
        
        if already_paid:
            # Already paid — show download directly
            if st.button(" Download Report", key=f'dl_paid_{report_key}', help="Download your paid report"):
                with st.spinner("Generating report..."):
                    try:
                        pdf_path = generate_report(ticker=ticker)
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        st.success(" Here's your report!")
                        st.download_button(
                            label=" Save PDF",
                            data=pdf_bytes,
                            file_name=f'{ticker}_Research_Report.pdf',
                            mime="application/pdf",
                            key=f'dl_save_{report_key}',
                        )
                    except Exception as e:
                        st.error(f"Report generation failed: {e}")
        else:
            # Check if payment just completed (returned from Stripe)
            query_params = st.query_params
            if query_params.get('payment') == 'success' and query_params.get('session_id', '') and query_params.get('ticker', '') == ticker:
                session_id = query_params['session_id']
                with st.spinner("Verifying payment..."):
                    result = verify_payment(session_id)
                    if result.get('verified'):
                        st.session_state.payment_verified[ticker] = True
                        st.success(f" Payment confirmed! Thank you for your purchase.")
                        # Generate and show download
                        try:
                            pdf_path = generate_report(ticker=ticker)
                            with open(pdf_path, "rb") as f:
                                pdf_bytes = f.read()
                            st.download_button(
                                label=" Download Your Report (PDF)",
                                data=pdf_bytes,
                                file_name=f'{ticker}_Research_Report.pdf',
                                mime="application/pdf",
                                key=f'dl_paid_{report_key}',
                                type='primary',
                            )
                        except Exception as e:
                            st.error(f"Report generation failed: {e}")
                    else:
                        st.warning("Payment verification pending. Please try again or contact support.")
            
            # Show Buy button or payment link
            stripe_ok, stripe_msg = check_stripe_config()
            if stripe_ok:
                col_price = st.columns([3, 1])
                with col_price[0]:
                    if st.button(f"' Buy Report (RM{DEFAULT_PRICE_RM})", key=report_key,
                                help="Purchase 30-page institutional PDF report"):
                        from urllib.parse import urlencode
                        base_url = query_params.get('origin', 'http://localhost:8501')
                        if 'localhost' in base_url or '://' not in base_url:
                            base_url = 'http://localhost:8501'
                        success_url = f'{base_url}/?payment=success&session_id={{"CHECKOUT_SESSION_ID"}}&ticker={ticker}'
                        cancel_url = f'{base_url}/'
                        session = create_checkout_session(ipo, success_url, cancel_url)
                        if session:
                            st.markdown(f'''
                                <a href="{session.url}" target="_blank">
                                    <button style="background:#e94560;color:white;border:none;padding:8px 20px;
                                    border-radius:6px;font-size:14px;cursor:pointer;">
                                    ' Pay RM{DEFAULT_PRICE_RM} via Card/FPX
                                    </button>
                                </a>
                            ''', unsafe_allow_html=True)
                            st.caption("Secure payment via Stripe. Card, FPX, GrabPay accepted.")
                        else:
                            st.error("Payment service unavailable. Try again later.")
                with col_price[1]:
                    st.caption(f"RM{DEFAULT_PRICE_RM}")
            else:
                # Stripe not configured — show free demo version
                if st.button(f" Preview Report (FREE)", key=report_key,
                            help="Generate a free preview report"):
                    with st.spinner("Generating preview..."):
                        try:
                            pdf_path = generate_report(ticker=ticker)
                            with open(pdf_path, "rb") as f:
                                pdf_bytes = f.read()
                            st.success(" Preview ready!")
                            st.info("Note: For the full 30-page report, configure Stripe payment.")
                            st.download_button(
                                label=" Download Preview",
                                data=pdf_bytes,
                                file_name=f'{ticker}_Research_Preview.pdf',
                                mime="application/pdf",
                                key=f'dl_free_{report_key}',
                            )
                        except Exception as e:
                            st.error(f"Report generation failed: {e}")

        render_ipo_detail(ipo)


st.sidebar.markdown(
    f"""
    <div style="text-align:center; padding: 0.5rem 0;">
        <h1 style="font-size:1.5rem; margin:0;"> Bursa IPO</h1>
        <p style="color:{BURSA_GOLD}; font-weight:600; margin:0;">Alpha Screener</p>
        <hr style="margin:1rem 0; border-color:#ECF0F1;">
    </div>
    """,
    unsafe_allow_html=True,
)

scores = load_scores()
df = prepare_df(scores)

st.sidebar.markdown("### Database")
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

st.sidebar.markdown("---")
st.sidebar.markdown(
    f'<div style="text-align:center;font-size:0.75rem;color:#95A5A6;">'
    f'v2.0.0 · {datetime.now().strftime("%b %Y")}</div>',
    unsafe_allow_html=True,
)


if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False


st.title(" Bursa Malaysia IPO Browser")
st.markdown("*Automated pre-listing valuation and scoring for Malaysian IPOs*")

col_add, _ = st.columns([1, 3])
with col_add:
    if st.button(" Add New IPO", type="primary", width='stretch'):
        st.session_state.show_add_form = not st.session_state.show_add_form

if st.session_state.show_add_form:
    with st.expander(" Add New IPO", expanded=True):
        st.markdown("Fill in details to add a new IPO to the database.")
        with st.form("manual_ipo_form"):
            col1, col2 = st.columns(2)
            with col1:
                company = st.text_input("Company Name", placeholder="e.g. Alpha Tech Bhd", key="m_company")
                market = st.selectbox("Market", ["ACE", "Main", "LEAP"], key="m_market")
                sector = st.selectbox("Sector", [
                    "Technology", "Industrial / Industrial Products", "Property / Property Development",
                    "Healthcare", "Consumer / Consumer Products", "Construction",
                    "Energy / Oil & Gas", "Plantation", "Financial Services",
                    "REIT", "Telecommunications", "Transportation & Logistics",
                ], key="m_sector")
                offer_price = st.number_input("Offer Price (RM)", min_value=0.01, step=0.05, format="%.2f", key="m_price")
                market_cap = st.number_input("Market Cap (RM)", min_value=0.0, step=1_000_000.0, format="%.0f", key="m_mcap")
                pe_ratio = st.number_input("P/E Ratio", min_value=0.0, step=0.1, format="%.1f", key="m_pe")
                sector_avg_pe = st.number_input("Sector Avg P/E", min_value=0.0, step=0.1, format="%.1f", key="m_spe")
                oversub = st.number_input("Oversubscription Rate (x)", min_value=0.0, step=0.1, format="%.1f", key="m_osub")
            with col2:
                net_margin = st.number_input("Net Profit Margin %", min_value=-50.0, step=0.5, format="%.1f", key="m_margin")
                rev_cagr = st.number_input("Revenue CAGR (3yr) %", min_value=-50.0, step=0.5, format="%.1f", key="m_cagr")
                shariah = st.selectbox("Shariah Compliant", ["Yes", "No", "Unknown"], key="m_shariah")
                float_pct = st.slider("Public Float %", 0, 100, 25, key="m_float")
                total_shares = st.number_input("Total Shares", min_value=1, step=1_000_000, format="%d", key="m_shares")
                moratorium = st.number_input("Moratorium Period (years)", min_value=0.0, step=0.5, format="%.1f", key="m_mora")
                promoter_pct = st.number_input("Promoter Ownership %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f", key="m_prom")
                status = st.selectbox("Application Status", ["Open", "Closing", "Listed", "Pending"], key="m_status")

            submitted = st.form_submit_button(" Score & Save", type="primary", width='stretch')
            if submitted:
                if not company.strip():
                    st.error("Company name is required!")
                else:
                    ipo_data = {
                        "company_name": company, "market": market, "sector": sector,
                        "offer_price": offer_price, "market_cap": market_cap,
                        "pe_ratio": pe_ratio or None, "sector_avg_pe": sector_avg_pe or None,
                        "oversubscription_rate": oversub or None,
                        "proceeds_utilization": {},
                        "net_profit_margin": net_margin or None, "revenue_cagr_3yr": rev_cagr or None,
                        "shariah_compliant": None if shariah == "Unknown" else shariah == "Yes",
                        "moratorium_period_years": moratorium or None,
                        "promoter_ownership_pct": promoter_pct or None,
                        "total_shares": total_shares, "public_float_pct": float_pct,
                        "application_status": status, "listing_date": None,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "data_quality": "MANUAL",
                    }
                    result = calculate_alpha_score(ipo_data)
                    ipo_data["alpha_score"] = result["total_score"]
                    ipo_data["verdict"] = result["verdict"]
                    ipo_data["score_breakdown"] = result["breakdown"]

                    existing_scores = load_scores()
                    existing_names = {s.get("company_name", "").lower().strip() for s in existing_scores}
                    if company.lower().strip() in existing_names:
                        st.error(f" {company} is already in the database!")
                    else:
                        existing_scores.append(ipo_data)
                        save_scores(existing_scores)
                        st.success(f" {company} scored! Alpha: {result['total_score']:.1f}/100 → **{result['verdict']}**")
                        st.balloons()
                        st.session_state.show_add_form = False
                        st.rerun()


if not scores:
    st.info(" No IPOs yet. Click **'Add New IPO'** to get started.")
else:
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
    with col_f1:
        verdict_opts = sorted({s.get("verdict", "N/A") for s in scores})
        verdict_filter = st.multiselect("Verdict", verdict_opts, default=verdict_opts)
    with col_f2:
        sectors = sorted({s.get("sector", "N/A") for s in scores})
        sector_filter = st.multiselect("Sector", sectors, default=sectors)
    with col_f3:
        markets = sorted({s.get("market", "N/A") for s in scores})
        market_filter = st.multiselect("Market", markets, default=markets)
    with col_f4:
        shariah_filter = st.selectbox("Shariah", ["All", "Shariah", "Non-Shariah"])
    with col_f5:
        search = st.text_input(" Search Company", placeholder="Type name...")

    filtered = scores
    if verdict_filter:
        filtered = [i for i in filtered if i.get("verdict", "N/A") in verdict_filter]
    if sector_filter:
        filtered = [i for i in filtered if i.get("sector", "N/A") in sector_filter]
    if market_filter:
        filtered = [i for i in filtered if i.get("market", "N/A") in market_filter]
    if shariah_filter == "Shariah":
        filtered = [i for i in filtered if i.get("shariah_compliant") is True]
    elif shariah_filter == "Non-Shariah":
        filtered = [i for i in filtered if i.get("shariah_compliant") is False]
    if search:
        q = search.lower()
        filtered = [i for i in filtered if q in i.get("company_name", "").lower()]

    st.caption(f"Showing {len(filtered)} of {len(scores)} IPOs")

    if not filtered:
        st.info(" No IPOs match the current filters. Try adjusting your selection.")
    else:
        for ipo in filtered:
            render_card(ipo, scores)

st.markdown(
    f"""
    <div class="footer">
        Bursa IPO Alpha Screener · AI-powered analysis · Not financial advice<br>
        Data sourced from Bursa Malaysia, KLSE Screener & IPOWatch<br>
        v2.0.0 | Built with Streamlit + Plotly
    </div>
    """,
    unsafe_allow_html=True,
)
