"""
dashboard/views/login.py
─────────────────────────────────────────────────────────────────────────────
Two-stage auth flow:
  Stage 1 (landing) – Full marketing page with only Sign In / Register buttons.
  Stage 2 (auth)    – Dedicated full-screen auth card (login or register form).
"""

import streamlit as st
from dashboard.api_client import login, register


# ── Shared CSS ────────────────────────────────────────────────────────────────

def _inject_landing_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, sans-serif !important;
    }
    #MainMenu, footer, header { visibility: hidden; }

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background: var(--bg) !important;
    }

    .block-container {
        background: var(--bg) !important;
        padding-top: 0 !important;
        padding-left: 5% !important;
        padding-right: 5% !important;
        max-width: 1300px !important;
        margin: 0 auto !important;
    }

    /* ── Hero headline ── */
    .hero-headline {
        font-size: clamp(2rem, 4vw, 3.2rem);
        font-weight: 800;
        color: var(--text);
        line-height: 1.15;
        letter-spacing: -1px;
        margin-bottom: 18px;
    }
    .hero-headline span { color: #3b82f6; }

    hr { border-color: var(--border) !important; margin: 32px 0 !important; }
    .stat-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
    }
    .stat-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: var(--accent);
        letter-spacing: -0.5px;
    }
    .stat-label {
        font-size: .75rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: .08em;
        margin-top: 4px;
    }

    /* ── Feature pills ── */
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--accent-h);
        border: 1px solid var(--accent-h);
        border-radius: 20px;
        padding: 5px 14px;
        font-size: .78rem;
        color: var(--accent);
        margin: 4px 4px 4px 0;
        font-weight: 500;
    }

    /* ── How-it-works steps ── */
    .step-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 18px 20px;
    }
    .step-num {
        width: 28px; height: 28px;
        background: var(--accent);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: .78rem; font-weight: 700; color: #fff;
        margin-bottom: 10px;
    }

    hr { border-color: var(--border) !important; margin: 32px 0 !important; }
    </style>
    """, unsafe_allow_html=True)


def _inject_auth_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, sans-serif !important;
    }
    #MainMenu, footer, header { visibility: hidden; }

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .block-container {
        background: var(--bg) !important;
        padding-top: 0 !important;
        max-width: 100% !important;
    }

    /* Form inputs */
    div[data-testid="stTextInput"] label {
        font-size: .82rem !important;
        font-weight: 500 !important;
        color: var(--muted) !important;
    }
    div[data-testid="stTextInput"] input {
        border-radius: 7px !important;
        border: 1px solid var(--border) !important;
        background: var(--input-bg) !important;
        color: var(--text) !important;
        font-size: .9rem !important;
        padding: 9px 12px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px var(--accent-h) !important;
    }

    /* ── Button System ── */
    
    /* 1. Global Primary Style (Active tab & CTA) */
    div[data-testid="stButton"] button[kind="primary"] {
        background: var(--accent) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        opacity: 0.9 !important;
        box-shadow: 0 4px 12px var(--accent-h) !important;
    }

    /* 2. Global Secondary / Ghost Style (Back link & Inactive tab) */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important;
        color: var(--muted) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        width: 100% !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        color: var(--text) !important;
        border-color: var(--accent) !important;
        background: var(--accent-h) !important;
    }

    hr { border-color: var(--border) !important; margin: 12px 0 !important; }

    div[data-testid="stAlert"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 7px !important;
        color: var(--text) !important;
    }

    .demo-hint { font-size:.75rem; color:var(--muted); text-align:center; margin-top:8px; }
    </style>
    """, unsafe_allow_html=True)


# ── Session helpers ───────────────────────────────────────────────────────────

def _save_session(result: dict):
    st.session_state["token"]         = result["access_token"]
    st.session_state["user_id"]       = result["user_id"]
    st.session_state["user_name"]     = result["name"]
    st.session_state["user_email"]    = result["email"]
    st.session_state["authenticated"] = True


# ── Stage 1: Landing page ─────────────────────────────────────────────────────

def _show_landing():
    _inject_landing_css()

    st.markdown("<div style='height:5vh'></div>", unsafe_allow_html=True)

    # ── Top nav bar ──────────────────────────────────────────────────────
    nav_l, nav_r = st.columns([1, 1])
    with nav_l:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;padding:6px 0">
          <div style="font-size:1.35rem;font-weight:800;color:var(--accent);letter-spacing:-0.5px">
            🛡️ Detexa
          </div>
          <div style="font-size:.65rem;color:var(--muted);text-transform:uppercase;
                      letter-spacing:.1em;padding-top:3px">
            Fraud Detection Platform
          </div>
        </div>
        """, unsafe_allow_html=True)
    
    with nav_r:
        r1, r2 = st.columns([4, 1])
        with r2:
            dark_mode = st.session_state.get("dark_mode", True)
            icon = "🌙" if dark_mode else "☀️"
            if st.button(icon, key="theme_toggle_landing", help="Toggle Dark/Light Mode"):
                st.session_state["dark_mode"] = not dark_mode
                st.rerun()

    st.markdown("<div style='height:5vh'></div>", unsafe_allow_html=True)

    # ── Hero ─────────────────────────────────────────────────────────────
    hero_l, hero_r = st.columns([1.1, 1], gap="large")
    with hero_l:
        st.markdown("""
        <div class="hero-headline">
          Protect your business<br>
          from <span>financial fraud.</span>
        </div>
        <p style="color:#64748b;font-size:.95rem;line-height:1.7;max-width:480px;margin-bottom:28px">
          Real-time credit card fraud scoring and behavioural anomaly
          detection, powered by machine learning.
        </p>
        """, unsafe_allow_html=True)

        # Feature pills
        st.markdown("""
        <div style="margin-bottom:32px">
          <span class="pill">⚡ Real-time Detection</span>
          <span class="pill">🤖 ML-Powered</span>
          <span class="pill">🔒 Behavioural Analysis</span>
          <span class="pill">📊 Unified Dashboard</span>
        </div>
        """, unsafe_allow_html=True)

        # CTA buttons
        cta1, cta2, _ = st.columns([1, 1, 0.6])
        with cta1:
            st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
            if st.button("🚀  Get Started", key="hero_start", use_container_width=True):
                st.session_state["auth_stage"] = "register"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with cta2:
            st.markdown('<div class="btn-secondary">', unsafe_allow_html=True)
            if st.button("Sign In →", key="hero_signin", use_container_width=True):
                st.session_state["auth_stage"] = "login"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with hero_r:
        # Stat cards
        st.markdown("""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px">
          <div class="stat-card">
            <div class="stat-value">97.7%</div>
            <div class="stat-label">AUC-ROC Accuracy</div>
            <div style="font-size:.7rem;color:#1e3a5f;margin-top:4px">Kaggle credit card dataset</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">&lt; 50 ms</div>
            <div class="stat-label">Response Time</div>
            <div style="font-size:.7rem;color:#1e3a5f;margin-top:4px">Per prediction via REST API</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">2</div>
            <div class="stat-label">Detection Models</div>
            <div style="font-size:.7rem;color:#1e3a5f;margin-top:4px">Credit fraud + behaviour anomaly</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">REST</div>
            <div class="stat-label">Integration</div>
            <div style="font-size:.7rem;color:#1e3a5f;margin-top:4px">Drop-in FastAPI backend</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── What is Detexa ───────────────────────────────────────────────────
    info_l, info_r = st.columns([1, 1], gap="large")
    with info_l:
        st.markdown("""
        <div style="margin-bottom:8px;font-size:1.2rem;font-weight:700;color:#f1f5f9">
          What is Detexa?
        </div>
        <p style="color:#64748b;font-size:.87rem;line-height:1.75">
          Detexa is an AI-powered fraud detection platform that helps organisations
          identify and respond to suspicious financial activity and anomalous user
          behaviour — before damage occurs.
        </p>
        """, unsafe_allow_html=True)

    with info_r:
        st.markdown("""
        <div style="margin-bottom:12px;font-size:1rem;font-weight:700;color:#f1f5f9">
          How it works
        </div>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div class="step-card">
            <div style="font-size:.88rem;font-weight:600;color:#93c5fd">01  Transaction scoring</div>
            <div style="font-size:.78rem;color:#64748b;margin-top:3px">
              XGBoost model analyses 28 PCA-transformed features to assign a fraud probability.
            </div>
          </div>
          <div class="step-card">
            <div style="font-size:.88rem;font-weight:600;color:#93c5fd">02  Behavioural analysis</div>
            <div style="font-size:.78rem;color:#64748b;margin-top:3px">
              Isolation Forest detects unusual login patterns — VPN use, typing speed, timing.
            </div>
          </div>
          <div class="step-card">
            <div style="font-size:.88rem;font-weight:600;color:#93c5fd">03  Alerts &amp; dashboard</div>
            <div style="font-size:.78rem;color:#64748b;margin-top:3px">
              Unified alert inbox with risk triage, SHAP explanations, and CSV export.
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:32px 0 16px;font-size:.72rem;color:#1e3a5f">
      © 2026 Detexa — AI Fraud Detection Platform
    </div>
    """, unsafe_allow_html=True)


# ── Stage 2: Auth form page ───────────────────────────────────────────────────

def _show_auth_form():
    _inject_auth_css()

    # Starting tab is whatever triggered the navigation
    st.session_state.setdefault("auth_tab", st.session_state.get("auth_stage", "login"))
    tab = st.session_state["auth_tab"]

    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)

    _, card_col, _ = st.columns([1, 1.1, 1])

    with card_col:
        # ── Back link ────────────────────────────────────────────────────────
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("← Back to home", key="back_home", 
                         use_container_width=True, type="secondary"):
                st.session_state.pop("auth_stage", None)
                st.session_state.pop("auth_tab", None)
                st.rerun()

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        # ── Brand & Theme Toggle ─────────────────────────────────────────────
        t1, t2 = st.columns([5, 1])
        with t1:
            st.markdown("""
            <div style="text-align:left;margin-bottom:24px">
              <div style="font-size:1.6rem;font-weight:800;color:var(--accent);letter-spacing:-0.5px">
                🛡️ Detexa
              </div>
              <div style="font-size:.72rem;color:var(--muted);text-transform:uppercase;
                          letter-spacing:.1em;margin-top:2px">
                Fraud Detection Platform
              </div>
            </div>
            """, unsafe_allow_html=True)
        with t2:
            dark_mode = st.session_state.get("dark_mode", True)
            icon = "🌙" if dark_mode else "☀️"
            if st.button(icon, key="theme_toggle_auth"):
                st.session_state["dark_mode"] = not dark_mode
                st.rerun()

        # ── Auth card ─────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="background:var(--card);border:1px solid var(--border);border-radius:14px;
                    padding:32px 32px 8px 32px">
        """, unsafe_allow_html=True)

        header_text = "Welcome back" if tab == "login" else "Create an account"
        sub_text    = "Sign in to continue to your dashboard" if tab == "login" \
                      else "Join Detexa to start detecting fraud"
        st.markdown(f"""
          <div style="font-size:1.15rem;font-weight:700;color:var(--text);margin-bottom:4px">
            {header_text}
          </div>
          <div style="font-size:.8rem;color:var(--muted);margin-bottom:22px">
            {sub_text}
          </div>
        """, unsafe_allow_html=True)

        # Tab switcher
        t1, t2 = st.columns(2)
        with t1:
            btn_type = "primary" if tab == "login" else "secondary"
            if st.button("Sign In", key="tab_si", 
                         use_container_width=True, type=btn_type):
                st.session_state["auth_tab"] = "login"
                st.rerun()
            
        with t2:
            btn_type = "primary" if tab == "register" else "secondary"
            if st.button("Register", key="tab_rg", 
                         use_container_width=True, type=btn_type):
                st.session_state["auth_tab"] = "register"
                st.rerun()

        st.markdown("---")

        # ── Login form ────────────────────────────────────────────────────────
        if tab == "login":
            email    = st.text_input("Email",    key="l_email", placeholder="you@example.com")
            password = st.text_input("Password", key="l_pw",    placeholder="••••••••",
                                     type="password")
            st.write("")
            if st.button("Sign In", key="btn_login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.warning("Please fill in both fields.")
                else:
                    with st.spinner("Signing in…"):
                        result = login(email, password)
                    if result:
                        _save_session(result)
                        st.session_state.pop("auth_stage", None)
                        st.session_state.pop("auth_tab", None)
                        st.rerun()
            st.markdown('<p class="demo-hint">Demo · admin@detexa.io / Admin@1234</p>',
                        unsafe_allow_html=True)

        # ── Register form ─────────────────────────────────────────────────────
        else:
            name      = st.text_input("Full name",         key="r_name",  placeholder="Jane Smith")
            reg_email = st.text_input("Email",             key="r_email", placeholder="jane@example.com")
            mobile    = st.text_input("Mobile (optional)", key="r_mob",   placeholder="+1 555 000 0000")
            reg_pass  = st.text_input("Password",          key="r_pw",
                                      placeholder="min 8 chars", type="password")
            confirm   = st.text_input("Confirm password",  key="r_cfm",
                                      placeholder="••••••••",    type="password")
            st.write("")
            if st.button("Create Account", key="btn_reg", use_container_width=True, type="primary"):
                if not all([name, reg_email, reg_pass, confirm]):
                    st.warning("Fill in all required fields.")
                elif reg_pass != confirm:
                    st.error("Passwords don't match.")
                elif len(reg_pass) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    with st.spinner("Creating account…"):
                        result = register(name, reg_email, mobile, reg_pass)
                    if result:
                        _save_session(result)
                        st.session_state.pop("auth_stage", None)
                        st.session_state.pop("auth_tab", None)
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)


# ── Public entry point ────────────────────────────────────────────────────────

def show_auth_page():
    """
    Called from app.py when the user is not authenticated.
    Routes between the landing page and the auth form based on session state.
    """
    auth_stage = st.session_state.get("auth_stage")  # None | "login" | "register"

    if auth_stage in ("login", "register"):
        _show_auth_form()
    else:
        _show_landing()
