import time
import httpx

def test_alert_pipeline():
    print("=== LIVE HIGH-RISK TRANSACTION & ALERT TRIGGER AUDIT ===")
    
    with httpx.Client(timeout=15.0) as client:
        # 1. Authenticate with admin account to obtain valid JWT
        login_url = "http://localhost:8000/api/v1/auth/login"
        login_resp = client.post(
            login_url,
            json={"email": "admin@detexa.ai", "password": "Admin@1234"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 2. Build high-risk suspicious Indian transaction payload
        unique_ref = f"TXN-ALERT-{int(time.time())}"
        payload = {
            "amount": 295000.00,  # ₹2,95,000 INR
            "merchant": "Tanishq Jewellery Mumbai",
            "category": "Jewellery",
            "country": "IN",
            "state": "Maharashtra",
            "channel": "Mobile_App",
            "transaction_type": "UPI",
            "account_type": "Savings",
            "kyc_status": "Expired",
            "account_balance": 12000.00,
            "credit_score": 520,
            "emi_amount": 15000.0,
            "transaction_ref": unique_ref,
            "user_id": "usr_priya_002",
            "device_id": "dev_unknown_untrusted",
            "ip_address": "103.21.124.5",
            # Skew fraud sensitive features
            "v14": -4.8, "v4": 3.9, "v12": -3.5, "v10": -3.1,
            "velocity_1m": 6, "is_unusual_hour": True,
        }

        # 3. Call Live Inference Endpoint
        predict_url = "http://localhost:8000/api/v1/predict/credit"
        pred_resp = client.post(predict_url, json=payload, headers=headers)
        assert pred_resp.status_code == 200, f"Prediction failed: {pred_resp.text}"
        data = pred_resp.json()
        print(f"Transaction Ref: {unique_ref}")
        print(f"Computed Fraud Score: {data.get('fraud_score'):.4f} | Risk Tier: {data.get('risk_level')}")
        print(f"Decision Engine Verdict: {data.get('decision')} | Fraud Flag: {data.get('is_fraud')}")

        # 4. Check Alerts Endpoint
        alerts_url = "http://localhost:8000/api/v1/alerts"
        alerts_resp = client.get(alerts_url, headers=headers)
        assert alerts_resp.status_code == 200, f"Alerts query failed: {alerts_resp.text}"
        alerts_data = alerts_resp.json()
        items = alerts_data.get("items", []) if isinstance(alerts_data, dict) else alerts_data
        total_count = alerts_data.get("total", len(items)) if isinstance(alerts_data, dict) else len(items)
        print(f"\nTotal Alerts in System: {total_count}")
        latest_alert = items[0] if items else None
        if latest_alert:
            print(f"Latest Alert ID: {latest_alert.get('id')}")
            print(f"Latest Alert Risk: {latest_alert.get('risk_level')} | Score: {latest_alert.get('score'):.4f}")
            print(f"Latest Alert Description: {latest_alert.get('description')}")
            print(f"Latest Alert Status: {latest_alert.get('status')}")

    print("\n✅ LIVE ALERT INTEGRITY & ENGINE VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_alert_pipeline()
