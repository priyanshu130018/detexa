"""
backend/scripts/test_resilience.py
─────────────────────────────────────────────────────────────────────────────
Resilience & Fault Injection Test Suite for Detexa:
Tests individual component failures and auto-recovery across 3 iterations each:
1. Redis Outage & Graceful Degradation (Repeated 3x)
2. Neo4j Outage & Graceful Degradation (Repeated 3x)
3. Kafka Outage & Streaming Fallback (Repeated 3x)

Verifies:
- Service survives failure without throwing unhandled 500 exceptions
- Graceful degradation and fallback to in-memory buffers/defaults
- Safe auto-recovery after container restart
- Zero unhandled crashes
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import httpx

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
RESULTS_PATH = backend_dir / "app" / "ml" / "saved" / "resilience_test_results.json"


def run_cmd(command: list[str]) -> tuple[int, str]:
    """Execute docker or system command synchronously"""
    try:
        res = subprocess.run(command, capture_output=True, text=True, timeout=60)
        return res.returncode, res.stdout.strip()
    except Exception as exc:
        return -1, str(exc)


def get_auth_token():
    """Register/login user to get valid JWT token"""
    with httpx.Client(timeout=10.0) as client:
        email = f"resilience_{uuid.uuid4().hex[:6]}@example.com"
        pwd = "ResiliencePassword123!"
        resp = client.post(
            f"{API_BASE_URL}/auth/register",
            json={"email": email, "password": pwd, "name": "Resilience Tester", "mobile": "+919999988888"},
        )
        if resp.status_code in (200, 201):
            return resp.json().get("access_token"), resp.json().get("user", {}).get("id")
        
        login_resp = client.post(
            f"{API_BASE_URL}/auth/login",
            data={"username": email, "password": pwd},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return login_resp.json().get("access_token"), login_resp.json().get("user_id")


def send_realtime_predict(token: str, user_id: str) -> tuple[int, dict]:
    """Send test transaction to realtime prediction endpoint"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "transaction_ref": f"RESIL-RT-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "amount": 1250.0,
        "transaction_amount": 1250.0,
        "currency": "INR",
        "merchant": "Swiggy India",
        "category": "Food_Dining",
        "merchant_category": "Food_Dining",
        "country": "IN",
        "device_fingerprint": "resil-dev-fp-123",
        "ip_address": "192.168.1.55",
        "account_type": "Savings",
        "transaction_type": "UPI",
        "channel": "Mobile_App",
        "kyc_status": "Verified",
        "transaction_hour": 14,
        "credit_score": 720,
        "account_balance": 85000.0,
    }
    with httpx.Client(timeout=10.0) as client:
        try:
            resp = client.post(f"{API_BASE_URL}/predict/realtime", json=payload, headers=headers)
            return resp.status_code, resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as exc:
            return 500, {"error": str(exc)}


def send_streaming_ingest(token: str, user_id: str) -> tuple[int, dict]:
    """Send test transaction to streaming ingestion endpoint"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "transaction_ref": f"RESIL-STRM-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "amount": 3500.0,
        "transaction_amount": 3500.0,
        "currency": "INR",
        "merchant": "Amazon India",
        "category": "Retail",
        "merchant_category": "Retail",
        "country": "IN",
        "device_fingerprint": "resil-dev-fp-456",
        "ip_address": "192.168.1.66",
        "account_type": "Savings",
        "transaction_type": "UPI",
        "channel": "Mobile_App",
        "kyc_status": "Verified",
        "transaction_hour": 16,
        "credit_score": 750,
        "account_balance": 120000.0,
    }
    with httpx.Client(timeout=10.0) as client:
        try:
            resp = client.post(f"{API_BASE_URL}/streaming/transactions", json=payload, headers=headers)
            return resp.status_code, resp.json() if resp.status_code in (200, 202) else {"error": resp.text}
        except Exception as exc:
            return 500, {"error": str(exc)}


def run_resilience_scenario(service_name: str, container_name: str, trial_idx: int, token: str, user_id: str) -> dict:
    """Execute failure injection, verify graceful fallback, restart, verify recovery"""
    print(f"\n[{service_name} Trial {trial_idx}/3] Starting Fault Injection Test...")

    # 1. Baseline Pre-Failure
    rt_status_pre, _ = send_realtime_predict(token, user_id)
    strm_status_pre, _ = send_streaming_ingest(token, user_id)

    # 2. Stop container
    print(f"  Stopping container '{container_name}'...")
    run_cmd(["docker", "stop", container_name])
    time.sleep(2.0)

    # 3. Test during failure (Graceful degradation verification)
    print(f"  Testing API during {service_name} outage...")
    rt_status_fail, rt_res_fail = send_realtime_predict(token, user_id)
    strm_status_fail, strm_res_fail = send_streaming_ingest(token, user_id)

    # Invariant: Must gracefully return valid status codes (200 / 202) without unhandled 500 crashes
    during_outage_healthy = (rt_status_fail == 200) and (strm_status_fail in (200, 202))

    # 4. Restart container
    print(f"  Restarting container '{container_name}'...")
    run_cmd(["docker", "start", container_name])
    time.sleep(5.0)  # Wait for health recovery

    # 5. Post-recovery verification
    print(f"  Testing API after {service_name} recovery...")
    rt_status_post, rt_res_post = send_realtime_predict(token, user_id)
    strm_status_post, strm_res_post = send_streaming_ingest(token, user_id)

    post_recovery_healthy = (rt_status_post == 200) and (strm_status_post in (200, 202))
    trial_passed = during_outage_healthy and post_recovery_healthy

    print(f"  -> Trial Result: {'PASSED' if trial_passed else 'FAILED'} (Degraded Gracefully: {during_outage_healthy}, Recovered: {post_recovery_healthy})")

    return {
        "service": service_name,
        "trial": trial_idx,
        "passed": trial_passed,
        "pre_outage": {"predict_realtime_status": rt_status_pre, "streaming_ingest_status": strm_status_pre},
        "during_outage": {
            "predict_realtime_status": rt_status_fail,
            "streaming_ingest_status": strm_status_fail,
            "graceful_degradation": during_outage_healthy,
        },
        "post_recovery": {
            "predict_realtime_status": rt_status_post,
            "streaming_ingest_status": strm_status_post,
            "recovered": post_recovery_healthy,
        },
    }


def main():
    print("=" * 70)
    print("DETEXA RESILIENCE & FAULT INJECTION VALIDATION")
    print("=" * 70)

    print("\nAuthenticating resilience testing agent...")
    token, user_id = get_auth_token()
    print(f"Authenticated. User ID: {user_id}")

    test_services = [
        {"name": "Redis", "container": "detexa_redis"},
        {"name": "Neo4j", "container": "detexa_neo4j"},
        {"name": "Kafka", "container": "detexa_kafka"},
    ]

    all_results = {}

    for s in test_services:
        service_trials = []
        print(f"\n======================================================================")
        print(f"Testing Fault Scenario: {s['name']} Failure & Auto-Recovery (3 Iterations)")
        print(f"======================================================================")
        for trial in range(1, 4):
            trial_res = run_resilience_scenario(
                service_name=s["name"],
                container_name=s["container"],
                trial_idx=trial,
                token=token,
                user_id=user_id,
            )
            service_trials.append(trial_res)
            time.sleep(2.0)

        all_results[s["name"]] = service_trials

    # Compile Final Resilience Report
    passed_count = sum(1 for trials in all_results.values() for t in trials if t["passed"])
    total_count = sum(len(trials) for trials in all_results.values())
    all_graceful = all(t["passed"] for trials in all_results.values() for t in trials)

    final_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_trials": total_count,
        "passed_trials": passed_count,
        "all_graceful_recovery": all_graceful,
        "scenarios": all_results,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    print(f"\n======================================================================")
    print(f"[+] RESILIENCE TESTING COMPLETE")
    print(f"   Total Trials Executed      : {total_count}")
    print(f"   Passed Trials              : {passed_count}/{total_count}")
    print(f"   Graceful Recovery Rate     : {((passed_count/total_count)*100):.2f}%")
    print(f"   Results saved to           : {RESULTS_PATH}")
    print(f"======================================================================")


if __name__ == "__main__":
    main()
