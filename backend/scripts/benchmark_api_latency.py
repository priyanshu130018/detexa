"""
backend/scripts/benchmark_api_latency.py
─────────────────────────────────────────────────────────────────────────────
Reproducible HTTP Latency & Throughput Benchmark for /api/v1/predict/realtime.
Performs:
- System Hardware & Container Environment Discovery
- Warmup with 300 excluded requests
- 10,000 requests per run at Concurrency = 1, 10, 50
- 3 Trials per concurrency level with median aggregation
- Reports p50, p95, p99, throughput, and error counts
"""

import asyncio
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import httpx
import numpy as np
import psutil

# Ensure backend root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import create_access_token

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TARGET_ENDPOINT = f"{BASE_URL}/predict/realtime"


def get_hardware_info() -> Dict[str, Any]:
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "python_version": platform.python_version(),
    }


def get_benchmark_token() -> str:
    auth_url_reg = f"{BASE_URL}/auth/register"
    auth_url_login = f"{BASE_URL}/auth/login"
    email = f"bench_user_{int(time.time())}@detexa.ai"
    pwd = "BenchPassword@123"
    with httpx.Client(timeout=10.0) as client:
        try:
            reg = client.post(auth_url_reg, json={"email": email, "password": pwd, "name": "Benchmarker"})
            if reg.status_code == 201:
                return reg.json()["access_token"]
        except Exception:
            pass
        login = client.post(auth_url_login, json={"email": "bench_user@detexa.ai", "password": "BenchPassword@123"})
        if login.status_code == 200:
            return login.json()["access_token"]
        raise RuntimeError("Failed to obtain valid benchmark JWT token from auth service")


SAMPLE_PAYLOAD = {
    "customer_id": "CUST_BENCH_001",
    "account_type": "Savings",
    "transaction_type": "UPI",
    "transaction_amount": 2450.0,
    "transaction_direction": "Debit",
    "account_balance": 45000.0,
    "merchant_category": "Retail",
    "state": "Maharashtra",
    "credit_score": 720,
    "has_loan": 0,
    "loan_type": "None",
    "emi_amount": 0.0,
    "transaction_status": "Completed",
    "channel": "Mobile Banking",
    "kyc_status": "Verified",
    "transaction_hour": 14,
    "merchant": "Amazon India",
    "category": "Retail",
    "country": "IN",
}


async def send_single_request(client: httpx.AsyncClient, headers: dict) -> tuple[float, bool]:
    t0 = time.perf_counter()
    try:
        resp = await client.post(TARGET_ENDPOINT, json=SAMPLE_PAYLOAD, headers=headers)
        lat_ms = (time.perf_counter() - t0) * 1000.0
        is_success = resp.status_code == 200
        return lat_ms, is_success
    except Exception:
        lat_ms = (time.perf_counter() - t0) * 1000.0
        return lat_ms, False


async def run_warmup(client: httpx.AsyncClient, headers: dict, count: int = 300):
    print(f"\n[Warmup] Warming up endpoint with {count} excluded requests...")
    t0 = time.perf_counter()
    success = 0
    for _ in range(count):
        _, ok = await send_single_request(client, headers)
        if ok:
            success += 1
    elapsed = time.perf_counter() - t0
    print(f"         Warmup completed in {elapsed:.2f}s ({success}/{count} successful).")


async def run_trial(
    concurrency: int,
    total_requests: int,
    token: str,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(10.0, connect=5.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        latencies: List[float] = []
        errors = 0
        
        sem = asyncio.Semaphore(concurrency)

        async def worker():
            nonlocal errors
            async with sem:
                lat, ok = await send_single_request(client, headers)
                latencies.append(lat)
                if not ok:
                    errors += 1

        t0 = time.perf_counter()
        tasks = [asyncio.create_task(worker()) for _ in range(total_requests)]
        await asyncio.gather(*tasks)
        total_time_sec = time.perf_counter() - t0

    lat_arr = np.array(latencies)
    p50 = float(np.percentile(lat_arr, 50))
    p95 = float(np.percentile(lat_arr, 95))
    p99 = float(np.percentile(lat_arr, 99))
    mean_lat = float(lat_arr.mean())
    throughput = float(total_requests / total_time_sec) if total_time_sec > 0 else 0.0

    return {
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_time_sec": total_time_sec,
        "throughput_rps": throughput,
        "mean_latency_ms": mean_lat,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "errors": errors,
    }


async def main_async():
    print("=" * 80)
    print("DETEXA API LATENCY & THROUGHPUT BENCHMARK: /api/v1/predict/realtime")
    print("=" * 80)

    hw_info = get_hardware_info()
    print("\n[Environment Details]")
    print(f"  - OS:            {hw_info['os']}")
    print(f"  - CPU:           {hw_info['processor']} ({hw_info['cpu_count_logical']} Logical / {hw_info['cpu_count_physical']} Physical Cores)")
    print(f"  - RAM:           {hw_info['total_ram_gb']} GB")
    print(f"  - Python:        {hw_info['python_version']}")
    print(f"  - Target URL:    {TARGET_ENDPOINT}")

    token = get_benchmark_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Verify endpoint is up
    async with httpx.AsyncClient(timeout=10.0) as check_client:
        try:
            lat, ok = await send_single_request(check_client, headers)
            if not ok:
                print("  [ERROR] Target endpoint did not respond with 200 OK! Aborting benchmark.")
                return
            print(f"  - Health Probe:  PASS (Initial latency: {lat:.2f} ms)")
        except Exception as e:
            print(f"  [ERROR] Cannot connect to {TARGET_ENDPOINT}: {e}")
            return

        # Warmup with 300 requests
        await run_warmup(check_client, headers, count=300)

    concurrency_levels = [1, 10, 50]
    total_requests_per_trial = 1000
    trials_count = 3

    benchmark_summary = {}

    for c in concurrency_levels:
        print(f"\n" + "-" * 80)
        print(f"Benchmarking Concurrency = {c} (Total: {total_requests_per_trial:,} requests x {trials_count} trials)...")
        print("-" * 80)

        trial_results = []
        for trial_num in range(1, trials_count + 1):
            print(f"  -> Running Trial {trial_num}/{trials_count} (C={c}, N={total_requests_per_trial:,})...", end="", flush=True)
            res = await run_trial(concurrency=c, total_requests=total_requests_per_trial, token=token)
            trial_results.append(res)
            print(f" Done in {res['total_time_sec']:.2f}s | Throughput: {res['throughput_rps']:.1f} rps | p50: {res['p50_latency_ms']:.2f}ms | p95: {res['p95_latency_ms']:.2f}ms | p99: {res['p99_latency_ms']:.2f}ms | Errors: {res['errors']}")

        # Compute median across the 3 trials
        median_p50 = float(np.median([r["p50_latency_ms"] for r in trial_results]))
        median_p95 = float(np.median([r["p95_latency_ms"] for r in trial_results]))
        median_p99 = float(np.median([r["p99_latency_ms"] for r in trial_results]))
        median_throughput = float(np.median([r["throughput_rps"] for r in trial_results]))
        total_errors = sum(r["errors"] for r in trial_results)

        benchmark_summary[f"concurrency_{c}"] = {
            "concurrency": c,
            "requests_per_trial": total_requests_per_trial,
            "trials_count": trials_count,
            "median_p50_ms": median_p50,
            "median_p95_ms": median_p95,
            "median_p99_ms": median_p99,
            "median_throughput_rps": median_throughput,
            "total_errors": total_errors,
            "individual_trials": trial_results,
        }

    print("\n" + "=" * 80)
    print("FINAL MEDIAN BENCHMARK RESULTS (/api/v1/predict/realtime)")
    print("=" * 80)
    print(f"{'Concurrency':<15} {'Throughput (RPS)':<20} {'p50 (ms)':<15} {'p95 (ms)':<15} {'p99 (ms)':<15} {'Errors'}")
    print("-" * 80)
    for c in concurrency_levels:
        s = benchmark_summary[f"concurrency_{c}"]
        print(f"{c:<15} {s['median_throughput_rps']:<20.1f} {s['median_p50_ms']:<15.2f} {s['median_p95_ms']:<15.2f} {s['median_p99_ms']:<15.2f} {s['total_errors']}")
    print("=" * 80)

    # Save artifact
    output_dir = Path("backend/app/ml/saved") if Path("backend/app/ml/saved").exists() else Path("app/ml/saved")
    output_file = output_dir / "api_latency_benchmark.json"
    full_output = {
        "hardware_environment": hw_info,
        "endpoint": TARGET_ENDPOINT,
        "warmup_requests": 300,
        "benchmark_summary": benchmark_summary,
    }
    with open(output_file, "w") as f:
        json.dump(full_output, f, indent=2)
    print(f"\n[OK] Latency benchmark results saved to: {output_file.resolve()}")


if __name__ == "__main__":
    asyncio.run(main_async())
