"""
dashboard/pages/alerts_page.py
─────────────────────────────────────────────────────────────────────────────
Alert management: list, filter, update status.
"""

import pandas as pd
import streamlit as st

from dashboard.api_client import get_alerts, update_alert_status

RED   = "#f75f5f"
AMBER = "#f7a84f"
GREEN = "#4fca8c"
BLUE  = "#4f8ef7"
SLATE = "#8b93a8"
CARD  = "var(--surface)"


def show_alerts():
    st.markdown("## 🔔 Alert Management")

    # ── Filters ───────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        status_f = st.selectbox("Status", ["All", "open", "reviewed", "resolved", "false_positive"])
    with c2:
        risk_f = st.selectbox("Risk level", ["All", "High", "Medium", "Low"])
    with c3:
        limit = st.select_slider("Limit", [50, 100, 200], value=100)

    status_param = None if status_f == "All" else status_f
    risk_param = None if risk_f == "All" else risk_f

    alerts = get_alerts(limit=limit, status=status_param, risk_level=risk_param)

    if not alerts:
        st.info("No alerts match your filters.")
        return

    # ── KPI row ───────────────────────────────────────────────────────────────
    df = pd.DataFrame(alerts)
    st.markdown("")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total", len(df))
    k2.metric("High Risk", int((df["risk_level"] == "High").sum()))
    k3.metric("Open", int((df["status"] == "open").sum()))
    k4.metric("Avg Score", f"{df['score'].mean():.3f}")
    st.markdown("---")

    # ── Alert cards ───────────────────────────────────────────────────────────
    for _, row in df.iterrows():
        risk = row.get("risk_level", "Low")
        color = {"High": RED, "Medium": AMBER, "Low": GREEN}.get(risk, SLATE)
        status = row.get("status", "open")
        status_color = {"open": RED, "reviewed": AMBER,
                        "resolved": GREEN, "false_positive": SLATE}.get(status, SLATE)
        score = row.get("score", 0)
        ts = str(row.get("created_at", ""))[:16].replace("T", " ")
        alert_type = row.get("alert_type", "")
        icon = "💳" if alert_type == "credit_fraud" else "👤"

        with st.expander(
            f"{icon}  [{risk}]  {row.get('description', '')}  — score {score:.3f}  |  {ts}",
            expanded=False,
        ):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.markdown(f"**Type:** `{alert_type}`  |  "
                            f"**Status:** <span style='color:{status_color}'>{status}</span>  |  "
                            f"**Score:** `{score:.4f}`",
                            unsafe_allow_html=True)
                if row.get("transaction_id"):
                    st.caption(f"Transaction: {row['transaction_id']}")
            with col_action:
                new_status = st.selectbox(
                    "Update status",
                    ["open", "reviewed", "resolved", "false_positive"],
                    index=["open", "reviewed", "resolved", "false_positive"].index(status)
                    if status in ["open", "reviewed", "resolved", "false_positive"] else 0,
                    key=f"sel_{row['id']}",
                )
                if st.button("Save", key=f"btn_{row['id']}", use_container_width=True):
                    result = update_alert_status(str(row["id"]), new_status)
                    if result:
                        st.success("Updated ✓")
                        st.rerun()

    # ── Timeline chart ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Alert Timeline")
    import plotly.express as px
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date
    timeline = df.groupby(["date", "risk_level"]).size().reset_index(name="count")
    if not timeline.empty:
        fig = px.area(
            timeline, x="date", y="count", color="risk_level",
            color_discrete_map={"High": RED, "Medium": AMBER, "Low": GREEN},
            template=st.session_state.get("plotly_template", "plotly_dark"),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0), height=260,
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)
