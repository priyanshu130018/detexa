"""
dashboard/pages/overview.py
─────────────────────────────────────────────────────────────────────────────
Main dashboard – KPI cards, daily/monthly charts, risk distribution.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import get_alerts, get_stats, get_transactions


# ── Color palette ─────────────────────────────────────────────────────────────
BLUE   = "#4f8ef7"
RED    = "#f75f5f"
AMBER  = "#f7a84f"
GREEN  = "#4fca8c"
SLATE  = "#8b93a8"
BG     = "#0f1117"
CARD   = "#1e2130"


def _kpi(label: str, value: str, delta: str = "", color: str = BLUE):
    st.markdown(f"""
    <div style="
        background:var(--surface);border-radius:12px;padding:20px 22px;
        border-left:4px solid {color};margin-bottom:8px;
        border-top: 1px solid var(--border);border-right: 1px solid var(--border);
        border-bottom: 1px solid var(--border);
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05)">
      <div style="font-size:.78rem;color:var(--muted);text-transform:uppercase;
                  letter-spacing:.08em;margin-bottom:6px">{label}</div>
      <div style="font-size:1.9rem;font-weight:700;color:var(--text);line-height:1">{value}</div>
      {f'<div style="font-size:.75rem;color:var(--muted);margin-top:4px">{delta}</div>' if delta else ''}
    </div>""", unsafe_allow_html=True)


def show_overview():
    st.markdown("## 📊 Overview")

    stats = get_stats()
    if not stats:
        st.info("No data yet. Run `python scripts/seed_data.py` to populate demo data.")
        return

    # ── KPI row ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _kpi("Total Transactions", f"{stats['total_transactions']:,}", color=BLUE)
    with c2:
        _kpi("Fraud Detected", f"{stats['fraud_count']:,}",
             f"{stats['fraud_rate']*100:.2f}% fraud rate", color=RED)
    with c3:
        _kpi("High Risk", f"{stats['high_risk_count']:,}", color=RED)
    with c4:
        _kpi("Open Alerts", f"{stats['open_alerts']:,}", color=AMBER)
    with c5:
        _kpi("Avg Fraud Score", f"{stats['avg_fraud_score']:.3f}", color=SLATE)

    st.markdown("---")

    # ── Load transactions ─────────────────────────────────────────────────────
    txns = get_transactions(limit=500)
    if not txns:
        st.info("No transactions found.")
        return

    df = pd.DataFrame(txns)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["hour"] = df["timestamp"].dt.hour

    # ── Row 1: Daily chart + Risk doughnut ────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("#### Daily Transactions (Last 30 Days)")
        daily = (
            df[df["timestamp"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)]
            .groupby(["date", "is_fraud"])
            .size()
            .reset_index(name="count")
        )
        daily["type"] = daily["is_fraud"].map({True: "Fraud", False: "Legitimate"})
        if not daily.empty:
            fig = px.bar(
                daily, x="date", y="count", color="type",
                color_discrete_map={"Fraud": RED, "Legitimate": BLUE},
                template=st.session_state.get("plotly_template", "plotly_dark"),
                labels={"date": "", "count": "Transactions", "type": ""},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.1), margin=dict(l=0, r=0, t=10, b=0),
                height=280,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("#### Risk Distribution")
        risk_counts = df["risk_level"].value_counts().reset_index()
        risk_counts.columns = ["risk", "count"]
        color_map = {"High": RED, "Medium": AMBER, "Low": GREEN, "None": SLATE}
        risk_counts["color"] = risk_counts["risk"].map(color_map)
        if not risk_counts.empty:
            fig2 = go.Figure(go.Pie(
                labels=risk_counts["risk"], values=risk_counts["count"],
                hole=0.62,
                marker=dict(colors=risk_counts["color"].tolist()),
                textinfo="percent+label",
                textfont_size=11,
            ))
            fig2.update_layout(
                template=st.session_state.get("plotly_template", "plotly_dark"),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=0, b=0),
                height=280,
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Row 2: Monthly report + Hourly heatmap ─────────────────────────────────
    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Monthly Report")
        monthly = (
            df.groupby("month")
            .agg(transactions=("id", "count"),
                 fraud=("is_fraud", "sum"),
                 avg_score=("fraud_score", "mean"))
            .reset_index()
        )
        monthly["fraud_rate"] = monthly["fraud"] / monthly["transactions"] * 100
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=monthly["month"], y=monthly["transactions"],
            name="Transactions", marker_color=BLUE, opacity=0.7,
        ))
        fig3.add_trace(go.Scatter(
            x=monthly["month"], y=monthly["fraud_rate"],
            name="Fraud Rate %", yaxis="y2",
            mode="lines+markers",
            line=dict(color=RED, width=2),
            marker=dict(size=6),
        ))
        fig3.update_layout(
            template=st.session_state.get("plotly_template", "plotly_dark"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis2=dict(overlaying="y", side="right", showgrid=False,
                        ticksuffix="%"),
            legend=dict(orientation="h", y=1.1),
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.markdown("#### Fraud Score Distribution")
        fraud_df = df[df["fraud_score"].notna()]
        if not fraud_df.empty:
            fig4 = go.Figure()
            fig4.add_trace(go.Histogram(
                x=fraud_df[fraud_df["is_fraud"] == False]["fraud_score"],
                name="Legitimate", marker_color=BLUE, opacity=0.7,
                xbins=dict(size=0.05),
            ))
            fig4.add_trace(go.Histogram(
                x=fraud_df[fraud_df["is_fraud"] == True]["fraud_score"],
                name="Fraud", marker_color=RED, opacity=0.8,
                xbins=dict(size=0.05),
            ))
            fig4.update_layout(
                barmode="overlay",
                template=st.session_state.get("plotly_template", "plotly_dark"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Fraud Score", yaxis_title="Count",
                legend=dict(orientation="h", y=1.1),
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
            )
            st.plotly_chart(fig4, use_container_width=True)

    # ── Recent alerts preview ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🔔 Recent Alerts")
    alerts = get_alerts(limit=8)
    if alerts:
        for a in alerts:
            risk = a.get("risk_level", "Low")
            color = {"High": RED, "Medium": AMBER, "Low": GREEN}.get(risk, SLATE)
            score = a.get("score", 0)
            ts = a.get("created_at", "")[:16].replace("T", " ")
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:14px;
                        background:var(--surface);border-radius:10px;padding:12px 16px;
                        margin-bottom:6px;border-left:3px solid {color};
                        border-top:1px solid var(--border);border-right:1px solid var(--border);
                        border-bottom:1px solid var(--border)">
              <span style="font-size:1rem;color:{color};font-weight:700;
                            min-width:60px">{risk}</span>
              <span style="flex:1;color:var(--text);font-size:.88rem">{a.get('description','')}</span>
              <span style="color:var(--muted);font-size:.78rem;white-space:nowrap">{ts}</span>
              <span style="background:{color}22;color:{color};border-radius:6px;
                            padding:2px 10px;font-size:.78rem;font-weight:600">
                {score:.2f}</span>
            </div>""", unsafe_allow_html=True)
