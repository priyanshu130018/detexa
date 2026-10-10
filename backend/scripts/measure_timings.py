import urllib.request
import json
import time
import sys

def measure():
    login_url = "http://localhost:8000/api/v1/auth/login"
    payload = json.dumps({"email": "admin@detexa.io", "password": "Admin@1234"}).encode("utf-8")
    
    print("=== MEASURING LOGIN API ===", flush=True)
    login_times = []
    token = None
    for i in range(5):
        t0 = time.perf_counter()
        req = urllib.request.Request(login_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                dur = (time.perf_counter() - t0) * 1000
                login_times.append(dur)
                token = data["access_token"]
                print(f"  Login run {i+1}: {dur:.2f} ms", flush=True)
        except Exception as e:
            print(f"  Login run {i+1} FAILED: {e}", flush=True)

    if login_times:
        print(f"Login API Average: {sum(login_times)/len(login_times):.2f} ms", flush=True)

    if not token:
        print("Could not obtain token, exiting.", flush=True)
        return

    headers = {"Authorization": f"Bearer {token}"}
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/alerts/stats"),
        ("GET", "/api/v1/dashboard/stats"),
        ("GET", "/api/v1/dashboard/trends?days=30"),
        ("GET", "/api/v1/dashboard/risk-distribution"),
        ("GET", "/api/v1/dashboard/categories"),
        ("GET", "/api/v1/dashboard/geo"),
        ("GET", "/api/v1/alerts?limit=6"),
        ("GET", "/api/v1/transactions?limit=50"),
        ("GET", "/api/v1/decisions/stats"),
    ]

    print("\n=== MEASURING DASHBOARD & RESOURCE APIS ===", flush=True)
    for method, ep in endpoints:
        times = []
        for r in range(3):
            t_start = time.perf_counter()
            req = urllib.request.Request(f"http://localhost:8000{ep}", headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=10) as res:
                    body = res.read()
                    dur = (time.perf_counter() - t_start) * 1000
                    times.append(dur)
            except Exception as e:
                dur = (time.perf_counter() - t_start) * 1000
                print(f"  {ep} run {r+1} FAILED ({dur:.2f} ms): {e}", flush=True)
        if times:
            print(f"  {ep}: avg {sum(times)/len(times):.2f} ms (runs: {[round(t, 1) for t in times]})", flush=True)

if __name__ == "__main__":
    measure()
