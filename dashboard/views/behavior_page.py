"""
dashboard/pages/behavior_page.py
─────────────────────────────────────────────────────────────────────────────
User behaviour analytics: IP/device tracking, anomaly distribution,
geo heatmap, session timeline.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import get_alerts, get_transactions

RED   = "#f75f5f"
AMBER = "#f7a84f"
GREEN = "#4fca8c"
BLUE  = "#4f8ef7"
SLATE = "#8b93a8"
CARD  = "var(--surface)"


def show_behavior():
    st.markdown("## 👤 Behaviour Analytics")

    # Fetch behaviour-type alerts as a proxy for behaviour logs
    alerts = get_alerts(limit=200)
    behavior_alerts = [a for a in alerts if a.get("alert_type") == "behavior_anomaly"]

    txns = get_transactions(limit=500)
    df_txn = pd.DataFrame(txns) if txns else pd.DataFrame()

    if not behavior_alerts and df_txn.empty:
        st.info("No behaviour data yet. Run seed_data.py first.")
        return

    # ── KPI strip ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Behaviour Alerts", len(behavior_alerts))
    high_b = sum(1 for a in behavior_alerts if a.get("risk_level") == "High")
    k2.metric("High Risk Sessions", high_b)
    open_b = sum(1 for a in behavior_alerts if a.get("status") == "open")
    k3.metric("Open", open_b)
    avg_score_b = (sum(a.get("score", 0) for a in behavior_alerts) / len(behavior_alerts)
                   if behavior_alerts else 0)
    k4.metric("Avg Anomaly Score", f"{avg_score_b:.3f}")

    st.markdown("---")

    col_l, col_r = st.columns(2)

    # ── Risk level pie ────────────────────────────────────────────────────────
    with col_l:
        st.markdown("#### Session Risk Distribution")
        if behavior_alerts:
            df_b = pd.DataFrame(behavior_alerts)
            vc = df_b["risk_level"].value_counts().reset_index()
            vc.columns = ["risk", "count"]
            color_map = {"High": RED, "Medium": AMBER, "Low": GREEN}
            fig = px.pie(vc, names="risk", values="count",
                         color="risk", color_discrete_map=color_map,
                         template=st.session_state.get("plotly_template", "plotly_dark"), hole=0.55)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=0, b=0), height=260,
                showlegend=True,
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No behaviour alert data.")

    # ── Anomaly score histogram ───────────────────────────────────────────────
    with col_r:
        st.markdown("#### Anomaly Score Distribution")
        if behavior_alerts:
            scores = [a.get("score", 0) for a in behavior_alerts]
            fig2 = go.Figure(go.Histogram(
                x=scores, nbinsx=20,
                marker_color=BLUE, opacity=0.8,
            ))
            fig2.add_vline(x=0.5, line_color=AMBER, line_dash="dash",
                           annotation_text="Medium threshold",
                           annotation_position="top right")
            fig2.add_vline(x=0.75, line_color=RED, line_dash="dash",
                           annotation_text="High threshold",
                           annotation_position="top right")
            fig2.update_layout(
                template=st.session_state.get("plotly_template", "plotly_dark"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Anomaly Score", yaxis_title="Sessions",
                margin=dict(l=0, r=0, t=10, b=0), height=260,
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ── Transaction country distribution ──────────────────────────────────────
    if not df_txn.empty and "country" in df_txn.columns:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### Transactions by Country")
            country_stats = (
                df_txn.groupby("country")
                .agg(total=("id", "count"),
                     fraud=("is_fraud", "sum"))
                .reset_index()
            )
            country_stats["fraud_rate"] = country_stats["fraud"] / country_stats["total"]
            fig3 = px.bar(
                country_stats.sort_values("total", ascending=False).head(12),
                x="country", y="total",
                color="fraud_rate",
                color_continuous_scale=["#4fca8c", "#f7a84f", "#f75f5f"],
                template=st.session_state.get("plotly_template", "plotly_dark"),
                labels={"total": "Transactions", "fraud_rate": "Fraud Rate"},
            )
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0), height=280,
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig3, use_container_width=True)

        with col_b:
            st.markdown("#### Transactions by Category")
            if "category" in df_txn.columns:
                cat_stats = (
                    df_txn.groupby("category")
                    .agg(total=("id", "count"), fraud=("is_fraud", "sum"))
                    .reset_index()
                )
                fig4 = px.bar(
                    cat_stats.sort_values("total", ascending=True),
                    x="total", y="category", orientation="h",
                    color="fraud",
                    color_continuous_scale=["#4f8ef7", "#f75f5f"],
                    template=st.session_state.get("plotly_template", "plotly_dark"),
                    labels={"total": "Count", "fraud": "Fraud Count"},
                )
                fig4.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=10, b=0), height=280,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig4, use_container_width=True)

    # ── Hourly activity heatmap (simulated) ───────────────────────────────────
    st.markdown("---")
    st.markdown("#### Login Hour Activity")
    if not df_txn.empty and "timestamp" in df_txn.columns:
        df_txn["timestamp"] = pd.to_datetime(df_txn["timestamp"])
        df_txn["hour"] = df_txn["timestamp"].dt.hour
        df_txn["dow"] = df_txn["timestamp"].dt.day_name()
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat = df_txn.groupby(["dow", "hour"]).size().reset_index(name="count")
        heat["dow"] = pd.Categorical(heat["dow"], categories=dow_order, ordered=True)
        heat = heat.sort_values("dow")
        fig5 = px.density_heatmap(
            heat, x="hour", y="dow", z="count",
            color_continuous_scale=["#0f1117", "#1e3a6b", "#4f8ef7"],
            template=st.session_state.get("plotly_template", "plotly_dark"),
            labels={"hour": "Hour of Day", "dow": "", "count": "Transactions"},
        )
        fig5.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0), height=260,
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ── Recent suspicious behaviour alerts ────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🚨 Suspicious Sessions")
    suspicious = [a for a in behavior_alerts if a.get("risk_level") in ("High", "Medium")][:10]
    if suspicious:
        for a in suspicious:
            risk = a.get("risk_level", "Low")
            color = RED if risk == "High" else AMBER
            score = a.get("score", 0)
            ts = str(a.get("created_at", ""))[:16].replace("T", " ")
            st.markdown(
                f"""<div style="background:{CARD};border-radius:10px;padding:12px 16px;
                                border-left:3px solid {color};margin-bottom:6px;
                                display:flex;align-items:center;gap:14px">
                  <span style="color:{color};font-weight:700;min-width:60px">{risk}</span>
                  <span style="flex:1;color:#c8ccd8;font-size:.87rem">{a.get('description','')}</span>
                  <span style="color:{SLATE};font-size:.76rem">{ts}</span>
                  <span style="background:{color}22;color:{color};border-radius:5px;
                               padding:2px 8px;font-size:.76rem;font-weight:600">{score:.3f}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("No high/medium risk sessions in current filter.")
