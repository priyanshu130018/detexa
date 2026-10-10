import concurrent.futures
import json
import os
import sys
import time
import uuid

import httpx
import numpy as np

BASE_URL = "http://localhost:8000"

def get_auth_token():
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@detexa.ai", "password": "Admin@1234"},
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        raise RuntimeError(f"Auth failed: {resp.text}")

def benchmark_endpoint(name, url, method="GET", payload_fn=None, headers=None, concurrency=1, total_requests=50):
    latencies = []
    errors = 0

    def single_req(client):
        try:
            t0 = time.perf_counter()
            if method == "POST":
                p = payload_fn() if payload_fn else {}
                r = client.post(url, json=p, headers=headers)
            else:
                r = client.get(url, headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            if r.status_code in [200, 201]:
                return lat, None
            return lat, f"HTTP {r.status_code}"
        except Exception as e:
            return 0.0, str(e)

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        with httpx.Client(timeout=10.0) as client:
            futures = [executor.submit(single_req, client) for _ in range(total_requests)]
            for fut in concurrent.futures.as_completed(futures):
                lat, err = fut.result()
                if err:
                    errors += 1
                else:
                    latencies.append(lat)

    total_duration = time.perf_counter() - t_start
    rps = total_requests / total_duration if total_duration > 0 else 0.0
    
    p50 = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95 = float(np.percentile(latencies, 95)) if latencies else 0.0
    p99 = float(np.percentile(latencies, 99)) if latencies else 0.0
    mean_lat = float(np.mean(latencies)) if latencies else 0.0

    return {
        "endpoint": name,
        "concurrency": concurrency,
        "total_requests": total_requests,
        "successful_requests": len(latencies),
        "failed_requests": errors,
        "duration_sec": round(total_duration, 2),
        "rps": round(rps, 1),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "mean_ms": round(mean_lat, 2),
        "error_rate_pct": round((errors / total_requests) * 100, 2),
    }

def run_load_tests():
    print("=================================================================")
    print("          BOUNDED API CONCURRENCY & LATENCY BENCHMARKS           ")
    print("=================================================================")

    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def sample_payload():
        return {
            "amount": round(500.0 + (uuid.uuid4().int % 50000) / 100, 2),
            "merchant": "Reliance Digital Mumbai",
            "category": "Electronics",
            "country": "IN",
            "state": "Maharashtra",
            "channel": "Mobile_App",
            "transaction_type": "UPI",
            "account_type": "Savings",
            "kyc_status": "Verified",
            "account_balance": 85000.00,
            "credit_score": 750,
            "emi_amount": 0.0,
            "transaction_ref": f"TXN-LOAD-{uuid.uuid4().hex[:8]}",
        }

    benchmarks = []
    concurrency_levels = [1, 10, 25]

    for c in concurrency_levels:
        print(f"\n--- Running Concurrency Level: {c} Clients ---")
        
        # 1. Prediction API
        res_pred = benchmark_endpoint(
            name="POST /api/v1/predict/credit",
            url=f"{BASE_URL}/api/v1/predict/credit",
            method="POST",
            payload_fn=sample_payload,
            headers=headers,
            concurrency=c,
            total_requests=50 if c < 25 else 75,
        )
        print(f"  [Predict API] RPS: {res_pred['rps']} | p50: {res_pred['p50_ms']}ms | p95: {res_pred['p95_ms']}ms | Err: {res_pred['error_rate_pct']}%")
        benchmarks.append(res_pred)

        # 2. Dashboard Stats API
        res_stats = benchmark_endpoint(
            name="GET /api/v1/dashboard/stats",
            url=f"{BASE_URL}/api/v1/dashboard/stats",
            method="GET",
            headers=headers,
            concurrency=c,
            total_requests=50 if c < 25 else 75,
        )
        print(f"  [Dashboard Stats] RPS: {res_stats['rps']} | p50: {res_stats['p50_ms']}ms | p95: {res_stats['p95_ms']}ms | Err: {res_stats['error_rate_pct']}%")
        benchmarks.append(res_stats)

        # 3. Alerts API
        res_alerts = benchmark_endpoint(
            name="GET /api/v1/alerts",
            url=f"{BASE_URL}/api/v1/alerts",
            method="GET",
            headers=headers,
            concurrency=c,
            total_requests=50 if c < 25 else 75,
        )
        print(f"  [Alerts List] RPS: {res_alerts['rps']} | p50: {res_alerts['p50_ms']}ms | p95: {res_alerts['p95_ms']}ms | Err: {res_alerts['error_rate_pct']}%")
        benchmarks.append(res_alerts)

    # Save benchmark report
    out_dir = "app/ml/saved" if os.path.exists("app/ml/saved") else "backend/app/ml/saved"
    out_file = os.path.join(out_dir, "api_load_benchmark_results.json")
    with open(out_file, "w") as f:
        json.dump(benchmarks, f, indent=2)
    print(f"\nSaved API benchmark results to {out_file}")
    print("=================================================================\n")

if __name__ == "__main__":
    run_load_tests()
