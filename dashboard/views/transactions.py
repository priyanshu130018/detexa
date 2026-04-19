"""
dashboard/pages/transactions.py
─────────────────────────────────────────────────────────────────────────────
Transactions table with filtering, search, and fraud row highlighting.
"""

import pandas as pd
import streamlit as st

from dashboard.api_client import get_transactions

RED   = "#f75f5f"
AMBER = "#f7a84f"
GREEN = "#4fca8c"
SLATE = "#8b93a8"


def _risk_badge(risk: str) -> str:
    colors = {"High": RED, "Medium": AMBER, "Low": GREEN}
    c = colors.get(risk, SLATE)
    return f'<span style="background:{c}22;color:{c};border-radius:5px;padding:2px 8px;font-size:.75rem;font-weight:600">{risk}</span>'


def show_transactions():
    st.markdown("## 💳 Transactions")

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        show_fraud = st.selectbox("Filter by type", ["All", "Fraud only", "Legitimate only"])
    with col2:
        risk_filter = st.selectbox("Risk level", ["All", "High", "Medium", "Low"])
    with col3:
        limit = st.select_slider("Max rows", options=[50, 100, 200, 500], value=200)
    with col4:
        search = st.text_input("Search merchant / ref", placeholder="e.g. Amazon")

    # ── Fetch ─────────────────────────────────────────────────────────────────
    is_fraud_param = None
    if show_fraud == "Fraud only":
        is_fraud_param = True
    elif show_fraud == "Legitimate only":
        is_fraud_param = False

    with st.spinner("Loading …"):
        txns = get_transactions(limit=limit, is_fraud=is_fraud_param)

    if not txns:
        st.info("No transactions found.")
        return

    df = pd.DataFrame(txns)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")

    # Apply front-end filters
    if risk_filter != "All":
        df = df[df["risk_level"] == risk_filter]
    if search:
        mask = (
            df["merchant"].fillna("").str.contains(search, case=False) |
            df["transaction_ref"].fillna("").str.contains(search, case=False)
        )
        df = df[mask]

    # ── Stats strip ───────────────────────────────────────────────────────────
    fraud_n = df["is_fraud"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Showing", f"{len(df):,} rows")
    c2.metric("Fraud", f"{fraud_n:,}")
    c3.metric("Fraud rate", f"{fraud_n/len(df)*100:.1f}%" if len(df) else "0%")
    c4.metric("Avg amount", f"${df['amount'].mean():.2f}" if len(df) else "$0")

    st.markdown("---")

    # ── Render table ──────────────────────────────────────────────────────────
    display_cols = ["transaction_ref", "timestamp", "amount",
                    "merchant", "category", "country",
                    "fraud_score", "risk_level", "is_fraud"]
    df_show = df[[c for c in display_cols if c in df.columns]].copy()
    df_show.columns = ["Ref", "Time", "Amount ($)", "Merchant",
                       "Category", "Country", "Score", "Risk", "Fraud"]

    # Colour rows
    def row_style(row):
        if row["Fraud"]:
            return [f"background-color: {RED}18; color: var(--text)"] * len(row)
        elif row["Risk"] == "Medium":
            return [f"background-color: {AMBER}12; color: var(--text)"] * len(row)
        return ["color: var(--muted)"] * len(row)

    styled = (
        df_show.style
        .apply(row_style, axis=1)
        .format({"Amount ($)": "${:.2f}", "Score": "{:.3f}"})
        .bar(subset=["Score"], color=f"{RED}66", vmin=0, vmax=1)
    )
    st.dataframe(styled, use_container_width=True, height=520)

    # ── CSV export ────────────────────────────────────────────────────────────
    csv = df_show.to_csv(index=False)
    st.download_button(
        "⬇ Export CSV", csv, "transactions.csv", "text/csv",
        use_container_width=False,
    )
