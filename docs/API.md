# Detexa API Reference

The Detexa REST API is mounted at `/api/v1`. Interactive OpenAPI/Swagger documentation and downloadable OpenAPI specs are available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc UI:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## 1. Authentication & Users

### 1.1 Register User
`POST /api/v1/auth/register`

Creates a new user account and returns an access token.

**Request Body:**
```json
{
  "email": "analyst@bank.com",
  "password": "SecurePassword123!",
  "full_name": "Jane Doe"
}
```

**Response (`201 Created`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "analyst@bank.com",
    "full_name": "Jane Doe",
    "is_active": true,
    "role": "analyst"
  }
}
```

### 1.2 Login (OAuth2 Password Bearer)
`POST /api/v1/auth/login`

**Request (Form URL Encoded):**
- `username`: `analyst@bank.com`
- `password`: `SecurePassword123!`

**Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "token_type": "bearer"
}
```

### 1.3 Get Current User Profile
`GET /api/v1/auth/me`  
*Header Required: `Authorization: Bearer <token>`*

**Response (`200 OK`):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "analyst@bank.com",
  "full_name": "Jane Doe",
  "role": "analyst"
}
```

---

## 2. Real-Time Transaction Ingestion

### 2.1 Ingest Transaction
`POST /api/v1/transactions`

Submits a financial transaction for real-time scoring, decisioning, and streaming broadcast.

**Request Body:**
```json
{
  "user_id": "usr_94a81b",
  "amount": 450.00,
  "currency": "USD",
  "merchant": "Electronics Depot Global",
  "category": "Electronics",
  "country": "US",
  "hour": 14,
  "device_fingerprint": "fp_88a91b04c",
  "ip_address": "198.51.100.42",
  "is_vpn": false,
  "is_tor": false
}
```

**Response (`201 Created`):**
```json
{
  "id": "tx_489b02a1ef80",
  "transaction_ref": "TXN-20261007-882194",
  "amount": 450.00,
  "currency": "USD",
  "timestamp": "2026-10-07T12:00:00Z",
  "fraud_score": 0.1245,
  "risk_level": "Low",
  "decision": "ALLOW",
  "prediction": {
    "id": "pred_981a72",
    "fraud_score": 0.1245,
    "risk_level": "Low",
    "decision": "ALLOW",
    "latency_ms": 0.38,
    "shap_values": [
      { "feature": "amount", "shap_value": -0.15 },
      { "feature": "velocity_1m", "shap_value": -0.08 }
    ]
  }
}
```

### 2.2 List Transactions (Paginated)
`GET /api/v1/transactions?page=1&limit=20&search=TXN&decision=BLOCK`

**Response (`200 OK`):**
```json
{
  "items": [ ... ],
  "total": 1450,
  "page": 1,
  "limit": 20,
  "total_pages": 73
}
```

### 2.3 Get Transaction by ID
`GET /api/v1/transactions/{id}`

Returns 360° transaction detail including related prediction, device, IP, and merchant records.

---

## 3. AI Prediction & Risk Inference

### 3.1 Single Credit Transaction Scoring
`POST /api/v1/predict/credit`

Performs low-latency XGBoost inference with real-time SHAP feature attributions.

**Request Body:**
```json
{
  "amount": 1250.00,
  "merchant": "Global Electronics",
  "category": "Electronics",
  "country": "US",
  "hour": 3,
  "is_vpn": true,
  "is_tor": false,
  "v1": -2.4,
  "v2": 1.8,
  "v3": -1.2,
  "v4": 3.5,
  "v14": -4.2
}
```

**Response (`200 OK`):**
```json
{
  "transaction_id": "tx_sim_98a72b",
  "transaction_ref": "TXN-SIM-982104",
  "fraud_score": 0.9421,
  "risk_level": "High",
  "is_fraud": true,
  "model_version": "xgboost-v3.0.0",
  "latency_ms": 0.42,
  "shap_top_features": [
    { "feature": "v14", "shap_value": 0.48 },
    { "feature": "v4", "shap_value": 0.32 },
    { "feature": "amount", "shap_value": 0.24 }
  ]
}
```

### 3.2 Batch Credit Fraud Scoring
`POST /api/v1/predict/credit/batch`

Scores up to 1,000 transaction vectors concurrently.

**Request Body:** Array of transaction objects.

**Response (`200 OK`):**
```json
{
  "total_processed": 100,
  "fraud_detected_count": 8,
  "batch_latency_ms": 12.4,
  "predictions": [ ... ]
}
```

### 3.3 Behavioral Anomaly Scoring
`POST /api/v1/predict/behavior`

Evaluates session telemetry with Isolation Forest.

**Request Body:**
```json
{
  "session_id": "sess_891b72a",
  "ip_address": "185.220.101.5",
  "login_hour": 3,
  "typing_speed": 12.5,
  "mouse_velocity": 450,
  "is_vpn": true,
  "is_tor": true,
  "failed_logins": 4,
  "device_change": true
}
```

**Response (`200 OK`):**
```json
{
  "session_id": "sess_891b72a",
  "anomaly_score": 0.865,
  "is_anomalous": true,
  "risk_level": "High",
  "risk_factors": [
    "TOR exit node detected",
    "High velocity typing anomaly (bot indicator)",
    "Frequent failed login attempts"
  ],
  "latency_ms": 0.52
}
```

---

## 4. Security Incident Alerts & Triage

### 4.1 List Security Alerts
`GET /api/v1/alerts?status=open&risk_level=High&limit=50`

**Response (`200 OK`):**
```json
[
  {
    "id": "alt_98a72b",
    "transaction_id": "tx_489b02a1ef80",
    "alert_type": "credit_fraud",
    "risk_level": "High",
    "score": 0.942,
    "description": "High value nocturnal transaction from Tor exit node.",
    "status": "open",
    "created_at": "2026-10-07T12:00:00Z",
    "shap_values": [ ... ]
  }
]
```

### 4.2 Update Alert Lifecycle Status
`PATCH /api/v1/alerts/{id}/status`

**Request Body:**
```json
{
  "status": "resolved",
  "notes": "Verified fraud with cardholder via out-of-band call."
}
```

---

## 5. Decision Engine & AI Governance

### 5.1 Evaluate Decision Context
`POST /api/v1/decisions/evaluate`

Evaluates real-time business policy rules against transaction context.

**Response (`200 OK`):**
```json
{
  "decision": "BLOCK",
  "triggered_rules": [
    {
      "rule_id": "RULE_VELOCITY",
      "rule_name": "Burst Velocity Exceeded",
      "severity": "CRITICAL",
      "action": "BLOCK",
      "message": "User exceeded 3 transactions in 1 minute."
    }
  ]
}
```

### 5.2 Manual Decision Override (Analyst Audit)
`POST /api/v1/decisions/{id}/override`

Allows authorized fraud analysts to override an AI verdict with mandatory audit justification.

**Request Body:**
```json
{
  "action": "ALLOW",
  "reason": "Customer pre-notified bank of international travel and luxury purchase."
}
```

---

## 6. Feature Store & Graph Endpoints

### 6.1 Feature Schema Metadata
`GET /api/v1/features/schema`

Returns definitions for the canonical 61-feature vector.

### 6.2 Redis Hot Velocity Lookup
`POST /api/v1/features/hot/{user_id}`

Retrieves sub-millisecond sliding window state for a user.

### 6.3 Subgraph Traversal
`GET /api/v1/graph/subgraph?entity_type=user&entity_key=usr_1001&depth=2`

Returns graph nodes and edges for visual rendering.

### 6.4 Detected Fraud Rings
`GET /api/v1/graph/fraud-rings?min_users=2&limit=20`

Returns detected fraud syndicates and collusion clusters.

---

## 7. Real-Time Streaming & WebSocket Channels

### 7.1 Server-Sent Events (SSE) Stream
`GET /api/v1/realtime/stream`

Continuous push stream distributing JSON event payloads:
- `event: transaction_created`
- `event: fraud_alert`
- `event: metrics_tick`

### 7.2 WebSocket Feeds
- **Live Transaction Feed:** `ws://localhost:8000/ws/transactions`
- **Security Incident Alerts:** `ws://localhost:8000/ws/alerts`

---

## 8. System Health & Diagnostics

- `GET /api/v1/health`: Liveness probe (`{"status": "healthy"}`).
- `GET /api/v1/readiness`: Readiness check verifying PostgreSQL, Redis, Kafka, and Neo4j connectivity.
- `GET /api/v1/models`: Returns metadata and performance metrics for registered ML models.
