"""
dashboard/api_client.py
─────────────────────────────────────────────────────────────────────────────
Thin HTTP client that wraps all calls to the FastAPI backend.
Tokens are stored in st.session_state.
"""

from typing import Any, Dict, List, Optional

import requests
import streamlit as st

API_BASE = "http://localhost:8000/api/v1"
TIMEOUT = 10


def _headers() -> Dict[str, str]:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get(path: str, params: Dict = None) -> Any:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to the API server. Make sure it's running on port 8000.")
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.session_state.clear()
            st.rerun()
        st.error(f"API error: {e}")
        return None


def _post(path: str, body: Dict) -> Any:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to the API server.")
        return None
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        st.error(f"Error: {detail}")
        return None


def _put(path: str, body: Dict) -> Any:
    try:
        r = requests.put(f"{API_BASE}{path}", json=body, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Error: {e}")
        return None


# ── Auth ──────────────────────────────────────────────────────────────────────

def login(email: str, password: str) -> Optional[Dict]:
    return _post("/auth/login", {"email": email, "password": password})


def register(name: str, email: str, mobile: str, password: str) -> Optional[Dict]:
    return _post("/auth/register", {"name": name, "email": email,
                                    "mobile": mobile, "password": password})


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_stats() -> Optional[Dict]:
    return _get("/alerts/stats")


def get_alerts(limit: int = 100, status: str = None, risk_level: str = None) -> List[Dict]:
    params = {"limit": limit}
    if status:
        params["status"] = status
    if risk_level:
        params["risk_level"] = risk_level
    return _get("/alerts", params=params) or []


def get_transactions(limit: int = 500, is_fraud: bool = None) -> List[Dict]:
    params = {"limit": limit}
    if is_fraud is not None:
        params["is_fraud"] = is_fraud
    return _get("/alerts/transactions", params=params) or []


def update_alert_status(alert_id: str, new_status: str) -> Optional[Dict]:
    return _put(f"/alerts/{alert_id}/status", {"status": new_status})


def predict_credit(payload: Dict) -> Optional[Dict]:
    return _post("/predict/credit", payload)


def predict_behavior(payload: Dict) -> Optional[Dict]:
    return _post("/predict/behavior", payload)
