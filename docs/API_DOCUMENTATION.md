# Detexa REST API Architecture & Endpoint Specification

## 1. Overview & Design Principles

The Detexa backend exposes an enterprise-grade, versioned REST API built on **FastAPI**. All operational endpoints are organized cleanly under `/api/v1`, enforcing strict separation of concerns across:
- **Routers**: Clean HTTP endpoint definitions (`app/api/v1/endpoints/`)
- **Schemas**: Pydantic v2 data validation and serialized response models (`app/models/schemas.py`)
- **Dependencies**: Inversion of control for DB sessions, authentication, and pagination (`app/api/deps.py`)
- **Services**: Business logic, ML orchestration, and Redis caching (`app/services/`)
- **Repositories**: Encapsulated data access and SQL joins (`app/repositories/`)
- **Exception Handlers**: Unified global error format (`app/core/exceptions.py`)

### Interactive OpenAPI Documentation
- **Swagger UI**: [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **ReDoc Interactive Reference**: [`http://localhost:8000/redoc`](http://localhost:8000/redoc)
- **OpenAPI 3.1 JSON Schema**: [`http://localhost:8000/api/v1/openapi.json`](http://localhost:8000/api/v1/openapi.json)

---

## 2. Standardized Formats & Conventions

### 2.1 HTTP Status Codes
- `200 OK`: Successful read or update operation.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Validation failure or malformed payload.
- `401 Unauthorized`: Missing or expired Bearer token.
- `403 Forbidden`: Insufficient permissions (e.g. non-admin accessing admin endpoints).
- `404 Not Found`: Target entity not found in the database.
- `422 Unprocessable Entity`: Pydantic schema validation violation.
- `500 Internal Server Error`: Unhandled database or server exception.
- `502 Bad Gateway`: ML model pipeline failure.

### 2.2 Standard Error Response (`ErrorResponse`)
All errors adhere to a uniform JSON payload structure:
```json
{
  "status_code": 404,
  "error_code": "TRANSACTION_NOT_FOUND",
  "message": "Transaction with identifier 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11' not found.",
  "details": null,
  "timestamp": "2026-10-06T17:20:00.000000Z",
  "path": "/api/v1/transactions/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

### 2.3 Standard Pagination (`PaginatedResponse[T]`)
List endpoints utilize typed pagination via `PaginationParams`:
- Query parameters: `page` (default 1), `page_size` (default 20, max 500).
- Response wrapper:
```json
{
  "items": [...],
  "total": 500,
  "page": 1,
  "page_size": 20,
  "pages": 25,
  "has_next": true,
  "has_prev": false
}
```

---

## 3. API Resource Reference

### 3.1 Authentication & Users (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Create user profile and receive JWT token | No |
| `POST` | `/api/v1/auth/login` | Authenticate email/password and receive JWT token | No |
| `GET` | `/api/v1/auth/me` | Retrieve authenticated user profile | Bearer |
| `GET` | `/api/v1/auth/users` | List platform users with pagination | Admin Bearer |
| `PATCH`| `/api/v1/auth/users/{user_id}/status` | Activate/deactivate user account | Admin Bearer |

---

### 3.2 Transactions (`/api/v1/transactions`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/transactions` | Paginated transactions with multi-field search & filters (`is_fraud`, `risk_level`, `min_amount`, `max_amount`, `start_date`, `end_date`, `search`) | Bearer |
| `GET` | `/api/v1/transactions/{transaction_id}` | Full transaction details with joined merchant, device, IP, and PCA features | Bearer |
| `GET` | `/api/v1/transactions/ref/{transaction_ref}` | Fetch transaction by unique business reference (`TXN-XXXX`) | Bearer |

---

### 3.3 AI Prediction & Risk Scoring (`/api/v1/predict`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/predict/credit` | Real-time ensemble ML fraud scoring, automated decision (`ALLOW`/`REVIEW`/`BLOCK`), and SHAP feature drivers | Bearer |
| `POST` | `/api/v1/predict/credit/batch` | High-throughput batch inference over arrays of transactions | Bearer |
| `POST` | `/api/v1/predict/behavior` | Session behavioral anomaly detection (keystroke cadence, mouse velocity, TOR/VPN reputation) | Bearer |

#### Single Credit Fraud Prediction Request Example:
```json
{
  "amount": 1250.00,
  "merchant": "LuxuryJewelers",
  "category": "luxury_goods",
  "country": "US",
  "v1": -1.3598, "v2": -0.07278, "v3": 2.5363, "v4": 1.3781,
  "v5": -0.3383, "v6": 0.4623, "v7": 0.2395, "v8": 0.0986,
  "v9": 0.3637, "v10": 0.0907, "v11": -0.5516, "v12": -0.6178,
  "v13": -0.9913, "v14": -0.3111, "v15": 1.4681, "v16": -0.4704,
  "v17": 0.2079, "v18": 0.0257, "v19": 0.4039, "v20": 0.2514,
  "v21": -0.0183, "v22": 0.2778, "v23": -0.1104, "v24": 0.0669,
  "v25": 0.1285, "v26": -0.1891, "v27": 0.1335, "v28": -0.0210
}
```

---

### 3.4 Alerts & Incident Triage (`/api/v1/alerts`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/alerts` | Paginated alerts with filters (`status`, `risk_level`, `alert_type`, `assigned_to`) | Bearer |
| `GET` | `/api/v1/alerts/{alert_id}` | Detailed alert record with linked transaction, user, and SHAP drivers | Bearer |
| `PATCH`| `/api/v1/alerts/{alert_id}/status` | Update alert triage status (`open`, `reviewed`, `resolved`, `false_positive`) | Bearer |
| `PUT`  | `/api/v1/alerts/{alert_id}/status` | Backward-compatible status update | Bearer |
| `PATCH`| `/api/v1/alerts/{alert_id}/assign` | Assign alert to security analyst | Bearer |
| `POST` | `/api/v1/alerts/{alert_id}/resolve` | Resolve alert with mandatory investigation notes | Bearer |
| `GET` | `/api/v1/alerts/stats` | High-level summary of alerts | Bearer |

---

### 3.5 Decisions & AI Governance (`/api/v1/decisions`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/decisions` | Paginated inference decision audit logs | Bearer |
| `GET` | `/api/v1/decisions/stats` | Breakdown of `ALLOW`, `REVIEW`, and `BLOCK` decision counts and percentages | Bearer |
| `GET` | `/api/v1/decisions/{decision_id}` | Detailed decision record | Bearer |
| `POST`| `/api/v1/decisions/{decision_id}/override` | Analyst manual override of automated AI decision with mandatory justification | Bearer |

---

### 3.6 Dashboard Analytics (`/api/v1/dashboard`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/dashboard/stats` | KPI summary: total txns, fraud count, fraud rate, open alerts, avg risk score | Bearer |
| `GET` | `/api/v1/dashboard/trends` | Time-series transaction and fraud trends for last N days | Bearer |
| `GET` | `/api/v1/dashboard/risk-distribution` | Distribution across Low, Medium, and High risk tiers | Bearer |
| `GET` | `/api/v1/dashboard/categories` | Industry category fraud risk breakdown | Bearer |
| `GET` | `/api/v1/dashboard/geo` | Geographic risk index and transaction counts by country | Bearer |

---

### 3.7 Behavioral Analytics (`/api/v1/behavior`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/behavior/logs` | Paginated behavioral telemetry logs with filters (`risk_level`, `is_vpn`, `is_tor`) | Bearer |
| `GET` | `/api/v1/behavior/logs/{log_id}` | Detailed session telemetry by log UUID | Bearer |
| `GET` | `/api/v1/behavior/stats` | Aggregate session metrics and anomaly rates | Bearer |

---

### 3.8 System Health & Model Registry (`/api/v1/system` & `/health`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Application liveness probe | No |
| `GET` | `/health/ready` | Readiness check verifying Database, Redis, and ML pipelines | No |
| `GET` | `/api/v1/system/health` | Liveness check under API router | No |
| `GET` | `/api/v1/system/readiness` | Readiness check under API router | No |
| `GET` | `/api/v1/system/models` | List active ML model versions, architectures, and evaluation metrics | Bearer |
