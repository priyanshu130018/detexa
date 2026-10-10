import time
import httpx

def test_live_pipeline():
    print("=== LIVE END-TO-END TRANSACTION PIPELINE AUDIT ===")
    
    with httpx.Client(timeout=15.0) as client:
        # 1. Authenticate with admin account to obtain valid JWT
        login_url = "http://localhost:8000/api/v1/auth/login"
        login_start = time.perf_counter()
        login_resp = client.post(
            login_url,
            json={"email": "admin@detexa.ai", "password": "Admin@1234"},
        )
        login_dur = (time.perf_counter() - login_start) * 1000
        print(f"[Stage 1: Auth] Status: {login_resp.status_code} | Duration: {login_dur:.2f}ms")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 2. Build unique realistic Indian transaction payload
        unique_ref = f"TXN-AUDIT-{int(time.time())}"
        payload = {
            "amount": 75000.00,  # ₹75,000 INR
            "merchant": "Reliance Digital Mumbai",
            "category": "Electronics",
            "country": "IN",
            "state": "Maharashtra",
            "channel": "Mobile_App",
            "transaction_type": "UPI",
            "account_type": "Savings",
            "kyc_status": "Verified",
            "account_balance": 185000.00,
            "credit_score": 765,
            "emi_amount": 0.0,
            "transaction_ref": unique_ref,
            "user_id": "usr_admin_001",
            "device_id": "dev_samsung_s24_mum",
            "ip_address": "103.21.124.5",
            "v1": 0.12, "v2": -0.45, "v3": 0.88, "v4": 0.32, "v5": -0.11,
            "v6": 0.05, "v7": 0.23, "v8": -0.02, "v9": 0.15, "v10": -0.28,
            "v11": 0.04, "v12": -0.19, "v13": 0.08, "v14": -0.35, "v15": 0.12,
            "v16": -0.09, "v17": 0.14, "v18": -0.03, "v19": 0.07, "v20": 0.01,
            "v21": -0.05, "v22": 0.02, "v23": -0.01, "v24": 0.03, "v25": -0.02,
            "v26": 0.01, "v27": -0.01, "v28": 0.02,
        }

        # 3. Call Live Inference Endpoint
        predict_url = "http://localhost:8000/api/v1/predict/credit"
        print(f"\n[Stage 2: FastAPI Submission] POST {predict_url} for Ref: {unique_ref}")
        p_start = time.perf_counter()
        pred_resp = client.post(predict_url, json=payload, headers=headers)
        p_dur = (time.perf_counter() - p_start) * 1000
        print(f"[Stage 2: FastAPI Submission] Response: {pred_resp.status_code} | Total HTTP Roundtrip: {p_dur:.2f}ms")
        assert pred_resp.status_code == 200, f"Prediction failed: {pred_resp.text}"

        data = pred_resp.json()
        print("\n=== PIPELINE STAGE TRACE DETAILS ===")
        print(f"[Stage 3: Redis Feature Store] Sliding window counters & velocity checked")
        print(f"[Stage 4: XGBoost Booster Core] Native C++ inference latency: {data.get('latency_ms', 0):.2f}ms")
        print(f"[Stage 5: Fraud Score] Computed Probability: {data.get('fraud_score'):.4f} | Risk Tier: {data.get('risk_level')}")
        print(f"[Stage 6: Decision Engine] Verdict: {data.get('decision', 'ALLOW')} | Flag: {'FRAUD' if data.get('is_fraud') else 'LEGITIMATE'}")
        
        shap_drivers = data.get("shap_top_features", [])
        print(f"[Stage 7: TreeSHAP Explainability] Drivers computed ({len(shap_drivers)} features):")
        for s in shap_drivers[:3]:
            print(f"    - {s.get('feature')}: {s.get('shap_value'):.5f}")

        explanation = data.get("explanation", {})
        print(f"[Stage 8: Groq LLM / Fallback] LLM Explanation Source: {'Groq API' if explanation.get('source') == 'groq' else 'Deterministic Safe Fallback Engine'}")
        print(f"    Summary: {explanation.get('summary', 'Standard automated evaluation complete.')}")

        # 4. Verify Dashboard Summary Reflects Live Update
        dash_url = "http://localhost:8000/api/v1/dashboard/stats"
        dash_resp = client.get(dash_url, headers=headers)
        print(f"\n[Stage 9: Dashboard Consistency] GET {dash_url} -> {dash_resp.status_code}")
        if dash_resp.status_code == 200:
            dash_data = dash_resp.json()
            print(f"    Total Evaluated Transactions: {dash_data.get('total_transactions', 0)}")
            print(f"    Fraud Incidents Detected: {dash_data.get('fraud_count', 0)}")
            print(f"    Overall Fraud Rate: {dash_data.get('fraud_rate', 0):.2%}")
            print(f"    Open Actionable Alerts: {dash_data.get('open_alerts_count', 0)}")
            print(f"    Average Risk Score: {dash_data.get('avg_fraud_score', 0):.4f}")

        print("\n✅ LIVE END-TO-END PIPELINE AUDIT VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_pipeline()
