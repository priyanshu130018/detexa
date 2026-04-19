"""
dashboard/app.py
─────────────────────────────────────────────────────────────────────────────
Detexa – Streamlit dashboard entry point.

Run with:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

# Add project root so dashboard.*, core.*, etc. resolve correctly.
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# ── Page config (must be FIRST Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Detexa – Fraud Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",   # sidebar hidden by default
)

# ── Deferred imports ──────────────────────────────────────────────────────────
from dashboard.views.login import show_auth_page
from dashboard.views.overview import show_overview
from dashboard.views.transactions import show_transactions
from dashboard.views.alerts_page import show_alerts
from dashboard.views.predict_page import show_predict
from dashboard.views.behavior_page import show_behavior


# ── Global CSS ────────────────────────────────────────────────────────────────

def _inject_global_css(dark: bool):
    # Determine palette based on theme
    if dark:
        bg, surface, border, text, muted, accent, accent_h, input_bg, card = (
            "#0f172a", "#1e293b", "#334155", "#f1f5f9", "#94a3b8", "#3b82f6", 
            "rgba(59,130,246,.10)", "#1e293b", "#1e293b"
        )
    else:
        bg, surface, border, text, muted, accent, accent_h, input_bg, card = (
            "#f8fafc", "#ffffff", "#e2e8f0", "#1e293b", "#64748b", "#2563eb", 
            "rgba(37,99,235,.08)", "#f1f5f9", "#ffffff"
        )

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ── CSS tokens ── */
    :root {{
        --bg:       {bg};
        --surface:  {surface};
        --border:   {border};
        --text:     {text};
        --muted:    {muted};
        --accent:   {accent};
        --accent-h: {accent_h};
        --input-bg: {input_bg};
        --card:     {card};
    }}

    /* ── Font ── */
    html, body, [class*="css"] {{
        font-family: 'Inter', system-ui, sans-serif !important;
    }}

    /* ── App background — hits both stApp and the outer wrapper ── */
    .stApp,
    .stApp > div,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="block-container"] {{
        background-color: var(--bg) !important;
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
    }}
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div {{
        color: var(--text) !important;
    }}

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header {{ visibility: hidden; }}
    div[data-testid="stDecoration"] {{ display: none; }}

    /* ── Typography ── */
    h1, h2, h3, h4, h5 {{
        color: var(--text) !important;
        font-weight: 700 !important;
        letter-spacing: -0.3px !important;
    }}
    p, li, span, label {{ color: var(--muted) !important; }}
    .stMarkdown p, .stMarkdown span {{ color: var(--text) !important; }}

    /* ── Metric cards ── */
    div[data-testid="metric-container"] {{
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px;
        padding: 20px !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important;
    }}
    div[data-testid="metric-container"] label {{
        color: var(--muted) !important;
        font-size: .75rem !important;
        text-transform: uppercase;
        letter-spacing: .06em;
    }}
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {{
        color: var(--text) !important;
        font-size: 1.65rem !important;
        font-weight: 700 !important;
    }}

    /* ── Sidebar nav buttons ── */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
        background: transparent !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        font-size: .9rem !important;
        font-weight: 500 !important;
        text-align: left !important;
        padding: 10px 16px !important;
        box-shadow: none !important;
        transition: all .15s ease !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {{
        background: var(--accent-h) !important;
        border-color: var(--accent) !important;
        color: var(--accent) !important;
    }}

    /* ── Javascript-tagged buttons ── */
    /* These classes are applied by the JS snippet below */
    
    .dt-primary-btn {{
        background: linear-gradient(135deg, var(--accent) 0%, #1d4ed8 100%) !important;
        color: #fff !important;
        border: none !important;
        box-shadow: 0 4px 14px var(--accent-h) !important;
        transform: translateY(0);
    }}
    .dt-primary-btn:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px var(--accent-h) !important;
        opacity: 0.95;
    }}

    .dt-secondary-btn {{
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}
    .dt-secondary-btn:hover {{
        background: var(--accent-h) !important;
        border-color: var(--accent) !important;
        color: var(--accent) !important;
        transform: translateY(-2px) !important;
    }}

    /* Theme Toggle - Target both by JS class and title attribute */
    .dt-toggle-btn, button[title*="Toggle"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 50% !important;
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        max-width: 44px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.25rem !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
        line-height: 1 !important;
        transition: all .2s ease !important;
    }}
    .dt-toggle-btn:hover, button[title*="Toggle"]:hover {{
        border-color: var(--accent) !important;
        transform: scale(1.08) rotate(10deg);
        background: var(--accent-h) !important;
        box-shadow: 0 6px 16px rgba(0,0,0,0.15) !important;
    }}
    .dt-toggle-btn p, button[title*="Toggle"] p {{
        margin: 0 !important;
        line-height: 1 !important;
    }}

    /* ── General buttons ── */
    div[data-testid="stButton"] > button {{
        border-radius: 7px !important;
        font-weight: 500 !important;
        font-size: .88rem !important;
        box-shadow: none !important;
        transition: all .12s ease !important;
    }}

    /* ── Text inputs ── */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {{
        background: var(--input-bg) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 7px !important;
        font-size: .9rem !important;
    }}
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label {{
        color: var(--muted) !important;
    }}

    /* ── Selectbox ── */
    div[data-baseweb="select"] {{
        background: var(--input-bg) !important;
    }}
    div[data-baseweb="select"] div {{
        background: var(--input-bg) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
    }}

    /* ── Tabs ── */
    div[data-testid="stTabs"] button {{
        font-weight: 500 !important;
        font-size: .88rem !important;
        color: var(--muted) !important;
    }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: var(--accent) !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        background: transparent !important;
        border-bottom: 1px solid var(--border) !important;
    }}

    /* ── DataFrames / tables ── */
    div[data-testid="stDataFrame"] {{
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid var(--border) !important;
    }}
    div[data-testid="stDataFrame"] * {{
        color: var(--text) !important;
        background-color: var(--surface) !important;
    }}

    /* ── Expanders ── */
    div[data-testid="stExpander"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }}
    div[data-testid="stExpander"] summary {{
        color: var(--text) !important;
    }}

    /* ── HR / dividers ── */
    hr {{ border-color: var(--border) !important; margin: 16px 0 !important; }}

    /* ── Alerts / info boxes ── */
    div[data-testid="stAlert"] {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
    }}

    /* ── Toggle ── */
    div[data-testid="stToggle"] label {{ color: var(--text) !important; }}

    /* ── Plotly charts background ── */
    .js-plotly-plot .plotly .bg {{ fill: var(--card) !important; }}

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
    </style>

    <script>
    function refreshUI() {{
        const btns = document.querySelectorAll('button');
        btns.forEach(btn => {{
            const text = (btn.innerText || btn.textContent || "").trim();
            if (text.includes("Get Started")) btn.classList.add('dt-primary-btn');
            if (text.includes("Sign In")) btn.classList.add('dt-secondary-btn');
            if (text.includes("Register")) btn.classList.add('dt-secondary-btn');
            if (text.includes("🌙") || text.includes("☀️")) btn.classList.add('dt-toggle-btn');
        }});
    }}
    if (!window.uiInterval) {{
        window.uiInterval = setInterval(refreshUI, 400);
    }}
    refreshUI();
    </script>
    """, unsafe_allow_html=True)

# ── Sidebar (hamburger style) ─────────────────────────────────────────────────

PAGES = [
    ("Overview",      "📊"),
    ("Transactions",  "💳"),
    ("Alerts",        "🔔"),
    ("Live Predict",  "🔍"),
    ("Behaviour",     "👤"),
]


def _sidebar(dark: bool) -> str:
    with st.sidebar:
        # Brand in sidebar
        st.markdown(f"""
        <div style="padding:8px 4px 20px 4px">
          <div style="font-size:1.15rem;font-weight:700;color:#3b82f6;letter-spacing:-0.3px">
            🛡️ Detexa
          </div>
          <div style="font-size:.7rem;color:#64748b;margin-top:2px;letter-spacing:.05em;text-transform:uppercase">
            Fraud Detection Platform
          </div>
        </div>
        """, unsafe_allow_html=True)

        # User badge
        name  = st.session_state.get("user_name", "User")
        email = st.session_state.get("user_email", "")
        st.markdown(f"""
        <div style="border-radius:8px;padding:10px 12px;margin-bottom:18px;
                    background:{'rgba(59,130,246,.1)' if dark else 'rgba(37,99,235,.06)'};
                    border:1px solid {'rgba(59,130,246,.2)' if dark else 'rgba(37,99,235,.12)'}">
          <div style="font-size:.88rem;font-weight:600;color:#3b82f6">{name}</div>
          <div style="font-size:.73rem;color:#64748b;margin-top:1px">{email}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div style="font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:8px">Navigation</div>', unsafe_allow_html=True)

        current = st.session_state.get("page", "Overview")
        for label, icon in PAGES:
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True):
                st.session_state["page"] = label
                st.rerun()

        st.markdown("---")

        # Dark mode
        new_dark = st.toggle("Dark mode", value=dark, key="dark_toggle")
        if new_dark != dark:
            st.session_state["dark_mode"] = new_dark
            st.rerun()

        st.markdown("---")

        if st.button("Sign out", key="signout_btn", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.markdown("""
        <div style="margin-top:32px;font-size:.68rem;color:#475569;text-align:center">
          Detexa v1.0.0
        </div>
        """, unsafe_allow_html=True)

    return st.session_state.get("page", "Overview")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Session defaults
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("dark_mode", True)
    st.session_state.setdefault("page", "Overview")
    # auth_stage: None = landing page, "login"/"register" = auth form
    if "auth_stage" not in st.session_state:
        st.session_state["auth_stage"] = None

    dark = st.session_state.get("dark_mode", True)

    # 1. Inject theme variables first
    _inject_global_css(dark)
    st.session_state["plotly_template"] = "plotly_dark" if dark else "plotly_white"

    # 2. Auth gate
    if not st.session_state.get("authenticated"):
        show_auth_page()
        return

    current = _sidebar(dark)

    if current == "Overview":
        show_overview()
    elif current == "Transactions":
        show_transactions()
    elif current == "Alerts":
        show_alerts()
    elif current == "Live Predict":
        show_predict()
    elif current == "Behaviour":
        show_behavior()


if __name__ == "__main__":
    main()
