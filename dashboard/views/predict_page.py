"""
dashboard/pages/predict_page.py
─────────────────────────────────────────────────────────────────────────────
Interactive prediction testing – credit fraud + behaviour anomaly.
"""

import random
import uuid

import streamlit as st

from dashboard.api_client import predict_behavior, predict_credit

RED   = "#f75f5f"
AMBER = "#f7a84f"
GREEN = "#4fca8c"
BLUE  = "#4f8ef7"
SLATE = "#8b93a8"
CARD  = "var(--surface)"


def _score_gauge(score: float, label: str):
    color = RED if score >= 0.75 else AMBER if score >= 0.5 else GREEN
    pct = int(score * 100)
    st.markdown(f"""
    <div style="background:var(--surface);border-radius:12px;padding:24px;text-align:center;
                border:1px solid var(--border);box-shadow:0 10px 15px -3px rgba(0,0,0,0.1)">
      <div style="font-size:.8rem;color:var(--muted);text-transform:uppercase;
                  letter-spacing:.08em;margin-bottom:12px">{label}</div>
      <div style="position:relative;width:140px;margin:0 auto">
        <svg viewBox="0 0 120 70" xmlns="http://www.w3.org/2000/svg" style="width:100%">
          <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="var(--border)" stroke-width="10" stroke-linecap="round"/>
          <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="{color}" stroke-width="10"
                stroke-linecap="round" stroke-dasharray="{pct*1.57},200" opacity=".9"/>
        </svg>
        <div style="position:absolute;bottom:4px;left:50%;transform:translateX(-50%);
                    font-size:1.9rem;font-weight:800;color:var(--text)">{score:.2f}</div>
      </div>
      <div style="margin-top:8px;font-size:.85rem;font-weight:600;color:{color}">
        {'🔴 HIGH RISK' if score>=0.75 else '🟡 MEDIUM RISK' if score>=0.5 else '🟢 LOW RISK'}
      </div>
    </div>""", unsafe_allow_html=True)


def _random_v():
    return round(random.gauss(0, 1), 4)


def show_predict():
    st.markdown("## 🔍 Live Prediction")

    tab_credit, tab_behavior = st.tabs(["💳 Credit Card Fraud", "👤 Behaviour Anomaly"])

    # ── Credit Fraud ──────────────────────────────────────────────────────────
    with tab_credit:
        st.markdown("#### Transaction Details")

        col1, col2, col3 = st.columns(3)
        with col1:
            amount = st.number_input("Amount ($)", min_value=0.01,
                                     max_value=50000.0, value=150.00, step=10.0)
            merchant = st.text_input("Merchant", value="Amazon")
            category = st.selectbox("Category",
                ["electronics", "travel", "food", "entertainment",
                 "clothing", "health", "gaming", "other"])
        with col2:
            country = st.selectbox("Country",
                ["US", "GB", "IN", "DE", "FR", "CA", "AU", "SG", "RU", "CN"])
            user_id = st.text_input("User ID (optional)", value="")
        with col3:
            st.markdown("**Randomise V-features**")
            st.caption("V1–V28 are PCA components from the Kaggle dataset.")
            use_fraud_pattern = st.checkbox("Simulate fraud pattern", value=False)

        # V features
        with st.expander("Advanced: V1–V28 features"):
            v_vals = {}
            cols = st.columns(7)
            for i in range(1, 29):
                col_idx = (i - 1) % 7
                with cols[col_idx]:
                    default = round(random.gauss(-2, 2), 3) if use_fraud_pattern else 0.0
                    v_vals[f"v{i}"] = st.number_input(f"V{i}", value=default,
                                                       format="%.3f", key=f"v{i}_credit")

        if st.button("🔍 Run Fraud Check", use_container_width=True, key="btn_credit"):
            payload = {
                "amount": amount,
                "merchant": merchant,
                "category": category,
                "country": country,
                **v_vals,
            }
            if user_id.strip():
                payload["user_id"] = user_id.strip()

            with st.spinner("Running model …"):
                result = predict_credit(payload)

            if result:
                st.markdown("---")
                rcol1, rcol2 = st.columns([1, 2])
                with rcol1:
                    _score_gauge(result["fraud_score"], "Fraud Score")
                with rcol2:
                    st.markdown(f"**Transaction ID:** `{result['transaction_id']}`")
                    st.markdown(f"**Risk Level:** `{result['risk_level']}`")
                    st.markdown(f"**Fraud Detected:** `{result['is_fraud']}`")
                    st.markdown(f"**Model Version:** `{result['model_version']}`")
                    st.markdown(f"**Latency:** `{result['latency_ms']:.1f} ms`")

                    if result.get("shap_top_features"):
                        st.markdown("**Top SHAP Features:**")
                        for feat in result["shap_top_features"][:5]:
                            bar_color = RED if feat["shap_value"] > 0 else GREEN
                            st.markdown(
                                f"`{feat['feature']}` → "
                                f"<span style='color:{bar_color}'>{feat['shap_value']:+.4f}</span>",
                                unsafe_allow_html=True,
                            )

    # ── Behaviour Anomaly ─────────────────────────────────────────────────────
    with tab_behavior:
        st.markdown("#### Session Behaviour")

        b1, b2, b3 = st.columns(3)
        with b1:
            session_id = st.text_input("Session ID",
                                        value=uuid.uuid4().hex[:16])
            ip_address = st.text_input("IP Address", value="192.168.1.1")
            geo_country = st.selectbox("Geo Country",
                ["US", "IN", "DE", "RU", "CN", "BR", "GB", "NG"])
            geo_city = st.text_input("City", value="New York")
        with b2:
            login_hour = st.slider("Login Hour (0–23)", 0, 23, 10)
            typing_speed = st.slider("Typing Speed (chars/sec)", 0.0, 15.0, 4.5, 0.1)
            mouse_velocity = st.slider("Mouse Velocity", 0.0, 600.0, 200.0, 10.0)
            failed_logins = st.slider("Failed Login Attempts", 0, 10, 0)
        with b3:
            is_vpn = st.checkbox("VPN Detected", value=False)
            is_tor = st.checkbox("TOR Detected", value=False)
            device_change = st.checkbox("Device Changed", value=False)
            device_fp = st.text_input("Device Fingerprint",
                                       value=uuid.uuid4().hex[:20])

        if st.button("🔍 Analyse Behaviour", use_container_width=True, key="btn_behavior"):
            payload = {
                "session_id": session_id,
                "ip_address": ip_address,
                "device_fingerprint": device_fp,
                "user_agent": "Mozilla/5.0",
                "login_hour": login_hour,
                "typing_speed": typing_speed,
                "mouse_velocity": mouse_velocity,
                "geo_country": geo_country,
                "geo_city": geo_city,
                "is_vpn": is_vpn,
                "is_tor": is_tor,
                "failed_logins": failed_logins,
                "device_change": device_change,
            }

            with st.spinner("Analysing …"):
                result = predict_behavior(payload)

            if result:
                st.markdown("---")
                rcol1, rcol2 = st.columns([1, 2])
                with rcol1:
                    _score_gauge(result["anomaly_score"], "Anomaly Score")
                with rcol2:
                    st.markdown(f"**Session ID:** `{result['session_id']}`")
                    st.markdown(f"**Risk Level:** `{result['risk_level']}`")
                    st.markdown(f"**Anomalous:** `{result['is_anomalous']}`")
                    st.markdown(f"**Latency:** `{result['latency_ms']:.1f} ms`")

                    flags = []
                    if is_tor:
                        flags.append("🔴 TOR exit node")
                    if is_vpn:
                        flags.append("🟡 VPN detected")
                    if device_change:
                        flags.append("🟡 Device change")
                    if failed_logins >= 3:
                        flags.append(f"🔴 {failed_logins} failed logins")
                    if login_hour < 5 or login_hour >= 22:
                        flags.append("🟡 Unusual login hour")
                    if flags:
                        st.markdown("**Risk Signals:**")
                        for f in flags:
                            st.markdown(f"- {f}")
