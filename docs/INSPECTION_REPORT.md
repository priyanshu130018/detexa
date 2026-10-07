# 🛡️ Detexa — Comprehensive Project Inspection & Architecture Report

> **Inspection Date:** 2026-10-06  
> **Target System:** Detexa AI-Powered Fraud Detection Platform  
> **Status:** Codebase Inspected (Zero Code Modified; Tests Not Run)  
> **Output File:** `docs/INSPECTION_REPORT.md`

---

## 📋 Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Section 1: Architecture Report](#2-section-1-architecture-report)
   - [2.1 High-Level System Architecture](#21-high-level-system-architecture)
   - [2.2 Data Flow & Request Lifecycles](#22-data-flow--request-lifecycles)
   - [2.3 Technology Stack & Versions](#23-technology-stack--versions)
   - [2.4 Service Boundaries & Separation of Concerns](#24-service-boundaries--separation-of-concerns)
3. [Section 2: Current Implementation Deep Dive](#3-section-2-current-implementation-deep-dive)
   - [3.1 Complete Folder & File Tree](#31-complete-folder--file-tree)
   - [3.2 Backend APIs & Routers](#32-backend-apis--routers)
   - [3.3 Business Logic & Services Layer](#33-business-logic--services-layer)
   - [3.4 Machine Learning Pipelines & Inference](#34-machine-learning-pipelines--inference)
   - [3.5 Database Schema & ORM Models](#35-database-schema--orm-models)
   - [3.6 Authentication & Authorization Audit](#36-authentication--authorization-audit)
   - [3.7 Frontend: Streamlit Dashboard](#37-frontend-streamlit-dashboard)
   - [3.8 Redis Usage & Caching Status](#38-redis-usage--caching-status)
   - [3.9 Docker & Infrastructure Configuration](#39-docker--infrastructure-configuration)
   - [3.10 Configuration & Environment Variables](#310-configuration--environment-variables)
   - [3.11 Test Suite Audit](#311-test-suite-audit)
   - [3.12 Reusable Utilities Catalog](#312-reusable-utilities-catalog)
4. [Section 3: Discovered Bugs & Architectural Flaws](#4-section-3-discovered-bugs--architectural-flaws)
   - [3.1 Critical Severity Flaws](#41-critical-severity-flaws)
   - [3.2 Major Severity Flaws](#42-major-severity-flaws)
   - [3.3 Moderate & Minor Severity Flaws](#43-moderate--minor-severity-flaws)
5. [Section 4: Missing Functionality Report](#5-section-4-missing-functionality-report)
   - [5.1 API & Backend Gaps](#51-api--backend-gaps)
   - [5.2 Machine Learning & Explainability Gaps](#52-machine-learning--explainability-gaps)
   - [5.3 Frontend Dashboard Gaps](#53-frontend-dashboard-gaps)
   - [5.4 Database, Migration & Caching Gaps](#54-database-migration--caching-gaps)
   - [5.5 Security & Production Readiness Gaps](#55-security--production-readiness-gaps)
6. [Section 5: Recommended Implementation Order & Roadmap](#6-section-5-recommended-implementation-order--roadmap)

---

## 1. Executive Summary

Detexa is designed as a hybrid fraud prevention and behavioral anomaly detection platform comprising a **FastAPI** REST backend, an **XGBoost / Isolation Forest** ML inference pipeline, a **PostgreSQL** relational database, an intended **Redis** caching/message layer, and a **Streamlit** dark-mode operations dashboard.

### Key Inspection Findings:
1. **Solid Foundation:** Clear modular structure across `api/`, `core/`, `database/`, `ml/`, `services/`, and `dashboard/`. Good use of Pydantic v2 schemas and modern typing.
2. **Critical Breaking Bugs Present:**
   - **Frontend Auth Header Missing on POST:** `dashboard/api_client.py` does not include bearer authorization headers in `_post()`, causing live predictions from the dashboard to fail against protected API endpoints.
   - **Hardcoded API URL in Container:** `dashboard/api_client.py` hardcodes `API_BASE = "http://localhost:8000/api/v1"`, ignoring the environment variable supplied in `docker-compose.yml` (`http://api:8000/api/v1`), which breaks Docker networking.
   - **Missing Feature Name Cache for SHAP:** `CreditFeatureEngineer` does not populate `_feature_names_cache`, causing feature explanations to fall back to synthetic placeholder names (`f0`, `f1`, etc.).
   - **Config Defaults & Settings Instantiation:** `core/config.py` uses `os.getenv()` as default values for settings attributes rather than letting Pydantic-Settings handle default values properly, causing `NoneType` issues when environment variables are omitted or when settings are cached.
3. **Zero Redis Implementation:** Despite Redis container definitions in `docker-compose.yml` and `requirements.txt`, no Python code connects to or utilizes Redis for caching, rate limiting, or session storage.
4. **Missing Database Migrations:** Alembic configuration exists, but no migration version scripts exist under `alembic/versions`. The application relies entirely on runtime `Base.metadata.create_all()`.

---

## 2. Section 1: Architecture Report

### 2.1 High-Level System Architecture

```mermaid
flowchart TD
    subgraph Client Layer
        Browser["User Browser / Ops Analyst"]
    end

    subgraph Presentation Layer
        Streamlit["Streamlit Dashboard (Port 8501)<br/>dashboard/app.py"]
        ApiClient["Dashboard API Client<br/>dashboard/api_client.py"]
    end

    subgraph API & Routing Layer
        FastAPI["FastAPI Gateway (Port 8000)<br/>api/main.py"]
        AuthMiddleware["Auth Middleware (JWT)<br/>api/middleware/auth_middleware.py"]
        AuthRouter["Auth Router<br/>/api/v1/auth/*"]
        PredictRouter["Predict Router<br/>/api/v1/predict/*"]
        AlertsRouter["Alerts Router<br/>/api/v1/alerts/*"]
    end

    subgraph Business Logic / Services Layer
        AuthSvc["AuthService<br/>services/auth_service.py"]
        FraudSvc["FraudDetectionService<br/>services/fraud_service.py"]
        BehaviorSvc["BehaviorDetectionService<br/>services/behavior_service.py"]
        AlertSvc["AlertService<br/>services/alert_service.py"]
    end

    subgraph Machine Learning Layer
        CreditModel["CreditFraudModel (Singleton)<br/>ml/models/credit_fraud_model.py"]
        CreditPipeline["Sklearn Pipeline + XGBoost<br/>ml/pipelines/feature_engineering.py"]
        SHAP["SHAP TreeExplainer"]
        BehaviorModel["BehaviorAnomalyModel (Singleton)<br/>ml/models/behavior_model.py"]
        IsoForest["Isolation Forest Anomaly Pipeline"]
    end

    subgraph Data & Storage Layer
        Postgres[(PostgreSQL 16 DB<br/>detexa_db)]
        RedisCache[(Redis 7 - UNUSED<br/>Port 6379)]
        LogFiles[("File Logs (Loguru)<br/>logs/detexa.log")]
    end

    Browser --> Streamlit
    Streamlit --> ApiClient
    ApiClient -->|HTTP REST / JSON| FastAPI
    FastAPI --> AuthMiddleware
    AuthMiddleware --> AuthRouter
    AuthMiddleware --> PredictRouter
    AuthMiddleware --> AlertsRouter

    AuthRouter --> AuthSvc
    PredictRouter --> FraudSvc
    PredictRouter --> BehaviorSvc
    AlertsRouter --> AlertSvc

    FraudSvc --> CreditModel
    CreditModel --> CreditPipeline
    CreditPipeline --> SHAP
    BehaviorSvc --> BehaviorModel
    BehaviorModel --> IsoForest

    AuthSvc --> Postgres
    FraudSvc --> Postgres
    BehaviorSvc --> Postgres
    AlertSvc --> Postgres
    FastAPI -.-> RedisCache
    FastAPI --> LogFiles
```

### 2.2 Data Flow & Request Lifecycles

#### A. Credit Card Fraud Prediction Flow
1. **Request Intake:** Client sends `POST /api/v1/predict/credit` with transaction payload (`amount`, `v1..v28`, optional `merchant`, `category`, `country`, `user_id`).
2. **Auth Verification:** `get_current_user` extracts Bearer JWT token from `Authorization` header, decodes payload using `SECRET_KEY`, queries `User` table to verify user existence and active status.
3. **Inference Execution:** `FraudDetectionService` delegates to singleton `CreditFraudModel.predict(payload)`:
   - Payload is normalized into a DataFrame.
   - `CreditFeatureEngineer.transform` computes derived features (`log_amount`, `amount_sq`, `V1_V2_interaction`, `V3_V4_interaction`, `V14_V17_interaction`, `v_norm`) and scales inputs.
   - XGBoost / Random Forest classifier runs `predict_proba`.
   - `SHAP.TreeExplainer` computes local feature importances.
4. **Risk Classification & Alert Generation:**
   - Fraud probability $\ge 0.75 \rightarrow \text{HIGH}$, $\ge 0.50 \rightarrow \text{MEDIUM}$, $< 0.50 \rightarrow \text{LOW}$.
   - If $\ge 0.50$ or score $> 0.40$, an `Alert` entity is staged.
5. **Persistence & Auditing:**
   - Generates and persists `Transaction` record.
   - Persists `Alert` record with SHAP values JSON payload.
   - Persists `PredictionLog` record containing latency and input SHA-256 hash.
   - Commits database transaction.
6. **Response Output:** Returns JSON `FraudPredictionOut` with score, risk level, classification, SHAP explanations, model version, and latency.

#### B. Behavioral Anomaly Detection Flow
1. **Request Intake:** Client sends `POST /api/v1/predict/behavior` with session metrics (`typing_speed`, `mouse_velocity`, `login_hour`, `is_vpn`, `is_tor`, `failed_logins`, `device_change`, `geo_country`, etc.).
2. **Auth Verification:** JWT bearer authentication.
3. **Inference Execution:** `BehaviorDetectionService` passes payload to `BehaviorAnomalyModel`:
   - `BehaviorFeatureEngineer` derives `is_night_login` and `risk_combo` flags and scales features.
   - `IsolationForest.score_samples` computes raw score.
   - Normalized anomaly score calculated: $\text{score} = \text{clip}(1.0 + \text{raw}, 0.0, 1.0)$.
4. **Persistence & Alert:**
   - Creates `BehaviorLog` record.
   - If anomaly score $\ge 0.50$, generates an `Alert` record.
   - Creates `PredictionLog` record.
5. **Response Output:** Returns JSON `BehaviorPredictionOut`.

#### C. Dashboard Operations Flow
1. **Authentication:** User logs in via `/api/v1/auth/login`. Token stored in Streamlit `st.session_state["token"]`.
2. **State & Polling:** Dashboard views call `dashboard/api_client.py` to fetch aggregated metrics (`/alerts/stats`), transaction lists (`/alerts/transactions`), and alerts (`/alerts`).
3. **Triage:** Analyst updates alert status via `PUT /alerts/{id}/status`, which sets status to `open`, `reviewed`, `resolved`, or `false_positive` and stamps `resolved_at`.

### 2.3 Technology Stack & Versions

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Backend API** | FastAPI | `0.111.0` | High-performance async ASGI web framework |
| **ASGI Server** | Uvicorn (standard) | `0.29.0` | ASGI application server |
| **ORM & Database** | SQLAlchemy | `2.0.30` | SQL abstraction and ORM modeling |
| **DB Driver** | psycopg2-binary | `2.9.9` | PostgreSQL driver |
| **DB Migrations** | Alembic | `1.13.1` | Schema revision and migration tool |
| **Data Validation** | Pydantic / Settings | `2.7.1` / `2.2.1` | Request/response validation & config |
| **Security & JWT** | python-jose / passlib | `3.3.0` / `1.7.4` | JWT encode/decode and bcrypt password hashing |
| **Machine Learning** | scikit-learn / XGBoost | `1.4.2` / `2.0.3` | Anomaly detection & gradient boosting models |
| **Explainability** | SHAP | `0.45.1` | Model interpretability (TreeExplainer) |
| **Data Resampling** | imbalanced-learn | `0.12.2` | SMOTE minority oversampling |
| **Model Serialization**| joblib | `1.4.2` | Pipeline pickling |
| **Frontend UI** | Streamlit | `1.34.0` | Interactive data application framework |
| **Visualizations** | Plotly / Altair | `5.22.0` / `5.3.0`| Interactive charts and gauges |
| **Logging** | Loguru | `0.7.2` | Structured, rotated file and console logger |
| **Cache (Planned)** | Redis | `5.0.4` | In-memory key-value store (currently unused) |

### 2.4 Service Boundaries & Separation of Concerns

```
┌────────────────────────────────────────────────────────────┐
│                        api/routers/                        │  <- Routing & HTTP Parsing
│               (auth.py, predict.py, alerts.py)             │
└─────────────────────────────┬──────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────┐
│                         services/                          │  <- Orchestration & Business Logic
│     (auth_service, fraud_service, behavior_service, etc.)  │
└──────────────┬──────────────────────────────┬──────────────┘
               │                              │
┌──────────────▼──────────────┐ ┌─────────────▼──────────────┐
│         database/           │ │            ml/             │
│      (models.py, db.py)     │ │ (credit_fraud, behavior)   │
└─────────────────────────────┘ └────────────────────────────┘
```

The system follows a 3-tier decoupled pattern:
- **Routers:** Handle HTTP status codes, parameter extraction, and dependency injection (`Depends(get_db)`, `Depends(get_current_user)`).
- **Services:** Contain transactional workflows, persistence logic, threshold evaluations, and model invocations.
- **Models / Pipelines:** Stateless domain logic, transformation steps, and model prediction logic.

---

## 3. Section 2: Current Implementation Deep Dive

### 3.1 Complete Folder & File Tree

```
Detexa/
├── .dockerignore                     # Docker build exclusion rules
├── .env                              # Active environment configuration
├── .env.example                      # Template environment configuration
├── .gitignore                        # Git ignore rules
├── alembic.ini                       # Alembic migration configuration
├── detexa.db                         # Local SQLite artifact (from local runs)
├── docker-compose.yml                # Multi-container orchestration definition
├── README.md                         # Project documentation
├── requirements.txt                  # Python dependencies pinned
├── test.db                           # Local test SQLite database
├── alembic/
│   ├── env.py                        # Migration environment script
│   └── __init__.py
├── api/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application factory & lifespan
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth_middleware.py        # OAuth2 password bearer JWT verification
│   └── routers/
│       ├── __init__.py
│       ├── alerts.py                 # Alert queries, updates, stats, transactions
│       ├── auth.py                   # Register, login, me endpoints
│       └── predict.py                # Credit & behavior prediction endpoints
├── core/
│   ├── __init__.py
│   ├── config.py                     # Pydantic Settings class
│   ├── logging.py                    # Loguru structured logger configuration
│   └── security.py                   # JWT & bcrypt helper functions
├── dashboard/
│   ├── __init__.py
│   ├── api_client.py                 # Backend HTTP API client wrapper
│   ├── app.py                        # Streamlit entry point, router, CSS themes
│   ├── components/
│   │   └── __init__.py               # Empty component package
│   └── views/
│       ├── __init__.py
│       ├── alerts_page.py            # Alert triage, status updates, timeline
│       ├── behavior_page.py          # Session anomaly charts & risk distributions
│       ├── login.py                  # Landing hero & auth modal forms
│       ├── overview.py               # Summary KPIs, daily/monthly charts
│       ├── predict_page.py           # Interactive prediction forms & gauges
│       └── transactions.py           # Data table, filters, CSV export
├── data/
│   └── creditcard.csv                # Kaggle credit card fraud dataset
├── database/
│   ├── __init__.py
│   ├── db.py                         # SQLAlchemy engine & session maker
│   └── models.py                     # ORM models (User, Transaction, Alert, etc.)
├── docker/
│   ├── Dockerfile.api                # Multi-stage build for FastAPI backend
│   └── Dockerfile.dashboard          # Streamlit frontend container image
├── logs/
│   └── detexa.log                    # Rotated runtime log file
├── ml/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── behavior_model.py         # Isolation Forest model wrapper
│   │   ├── credit_fraud_model.py     # XGBoost/RF wrapper with SHAP explainability
│   │   └── saved/
│   │       ├── behavior_pipeline.pkl      # Serialized behavior pipeline
│   │       └── credit_fraud_pipeline.pkl  # Serialized credit fraud pipeline
│   └── pipelines/
│       ├── __init__.py
│       └── feature_engineering.py   # Sklearn transformer classes
├── models/
│   ├── __init__.py
│   └── schemas.py                    # Pydantic v2 validation models
├── scripts/
│   ├── __init__.py
│   ├── seed_data.py                  # Synthetic data generator & DB seeder
│   └── train_models.py               # ML training script for both models
└── tests/
    ├── __init__.py
    └── test_api.py                   # Pytest API integration tests
```

### 3.2 Backend APIs & Routers

| Method | Endpoint | Auth Required | Request Body / Query | Response Model | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | No | None | `dict` | Liveness health check |
| `GET` | `/` | No | None | `JSONResponse` | Welcome message & docs link |
| `POST` | `/api/v1/auth/register` | No | `UserRegister` | `TokenResponse` | Creates user and returns JWT |
| `POST` | `/api/v1/auth/login` | No | `UserLogin` | `TokenResponse` | Validates credentials, updates `last_login`, returns JWT |
| `GET` | `/api/v1/auth/me` | Yes (User) | None | `UserOut` | Returns current user profile |
| `POST` | `/api/v1/predict/credit` | Yes (User) | `TransactionIn` | `FraudPredictionOut` | Runs credit fraud inference, logs txn/alert |
| `POST` | `/api/v1/predict/behavior`| Yes (User) | `BehaviorIn` | `BehaviorPredictionOut`| Runs anomaly inference, logs session/alert |
| `GET` | `/api/v1/alerts` | Yes (User) | `limit`, `skip`, `status`, `risk_level` | `List[AlertOut]` | Lists alerts with filtering |
| `PUT` | `/api/v1/alerts/{alert_id}/status` | Yes (User) | `AlertUpdate` | `AlertOut` | Updates alert state (`resolved_at` on resolved) |
| `GET` | `/api/v1/alerts/stats` | Yes (User) | None | `DashboardStats` | Aggregated dashboard KPI counts |
| `GET` | `/api/v1/alerts/transactions` | Yes (User) | `limit`, `skip`, `is_fraud` | `List[dict]` | Returns enriched transaction records |

### 3.3 Business Logic & Services Layer

1. **`AuthService` (`services/auth_service.py`):**
   - Validates uniqueness of user email.
   - Uses `hash_password()` (`passlib.context.CryptContext` with bcrypt).
   - Issues 60-minute JWT bearer token containing `sub` (User UUID) and `email`.
   - Rejects disabled (`is_active == False`) accounts.

2. **`FraudDetectionService` (`services/fraud_service.py`):**
   - Coordinates inference via `CreditFraudModel.get_instance().predict()`.
   - Classifies risk score: High ($\ge 0.75$), Medium ($\ge 0.50$), Low ($< 0.50$).
   - Automatically raises an `Alert` if `is_fraud == True` or `fraud_score > 0.40`.
   - Creates `Transaction`, `Alert`, and `PredictionLog` records in a single database transaction.

3. **`BehaviorDetectionService` (`services/behavior_service.py`):**
   - Coordinates inference via `BehaviorAnomalyModel.get_instance().predict()`.
   - Automatically raises an `Alert` when `is_anomalous == True` ($\text{anomaly\_score} \ge 0.50$).
   - Persists `BehaviorLog` and `PredictionLog` audit records.

4. **`AlertService` (`services/alert_service.py`):**
   - Manages pagination and SQL filters for alerts.
   - Computes SQL aggregate metrics (`func.count`, `func.avg`) over the `Transaction` and `Alert` tables for dashboard metrics.
   - Handles alert status lifecycle transitions and records `resolved_at` timestamps.

### 3.4 Machine Learning Pipelines & Inference

#### Model 1: Credit Card Fraud Classifier (`ml/models/credit_fraud_model.py`)
- **Type:** Supervised binary classification.
- **Model Algorithms:** XGBoost (`XGBClassifier`) with automatic fallback to `RandomForestClassifier`.
- **Pre-processing:** `CreditFeatureEngineer` (`ml/pipelines/feature_engineering.py`):
  - Normalizes case of feature keys (`v1` $\rightarrow$ `V1`, `amount` $\rightarrow$ `Amount`).
  - Engineers 6 derived features: `log_amount`, `amount_sq`, `V1_V2_interaction`, `V3_V4_interaction`, `V14_V17_interaction`, and `v_norm` ($L_2$ norm across all $V$ components).
  - Scales all numerical features via `StandardScaler`.
- **Imbalance Handling:** `SMOTE(sampling_strategy=0.1)` applied during training.
- **Explainability:** `shap.TreeExplainer` generates top-10 feature contribution values (`shap_values`) per prediction.
- **Serialization:** Sklearn `Pipeline([('features', CreditFeatureEngineer()), ('classifier', clf)])` saved to `ml/models/saved/credit_fraud_pipeline.pkl`.

#### Model 2: Behavioral Anomaly Detector (`ml/models/behavior_model.py`)
- **Type:** Unsupervised anomaly detection.
- **Algorithm:** `IsolationForest(n_estimators=200, contamination=0.05)`.
- **Pre-processing:** `BehaviorFeatureEngineer`:
  - Derives `is_night_login` (1 if hour $<6$ or $\ge 22$, else 0).
  - Derives `risk_combo` (`int(is_vpn) + int(is_tor) + int(device_change)`).
  - Scales features via `StandardScaler`.
- **Score Normalization:** Translates `score_samples()` into $[0, 1]$ anomaly probability:
  $$\text{score} = \text{clip}(1.0 + \text{raw\_score}, 0.0, 1.0)$$
- **Serialization:** Custom wrapper `BehaviorPipeline(feature_eng, clf)` serialized to `ml/models/saved/behavior_pipeline.pkl`.

### 3.5 Database Schema & ORM Models

The database schema is defined in `database/models.py` using SQLAlchemy 2.0 declarative models:

```mermaid
erDiagram
    users ||--o{ transactions : "makes"
    users ||--o{ behavior_logs : "generates"
    users ||--o{ alerts : "associated with"
    transactions ||--o| alerts : "triggers"

    users {
        uuid id PK
        string name
        string email UK
        string mobile
        string hashed_password
        boolean is_active
        boolean is_admin
        datetime created_at
        datetime last_login
    }

    transactions {
        uuid id PK
        uuid user_id FK
        string transaction_ref UK
        float amount
        float v1_through_v28
        string merchant
        string category
        string country
        string currency
        float fraud_score
        enum risk_level
        boolean is_fraud
        int label
        datetime timestamp
    }

    behavior_logs {
        uuid id PK
        uuid user_id FK
        string session_id
        string ip_address
        string device_fingerprint
        text user_agent
        int login_hour
        float typing_speed
        float mouse_velocity
        string geo_country
        string geo_city
        boolean is_vpn
        boolean is_tor
        int failed_logins
        boolean device_change
        float anomaly_score
        enum risk_level
        datetime created_at
    }

    alerts {
        uuid id PK
        uuid user_id FK
        uuid transaction_id FK
        string alert_type
        enum risk_level
        float score
        text description
        enum status
        json shap_values
        json metadata
        datetime created_at
        datetime resolved_at
    }

    prediction_logs {
        uuid id PK
        string endpoint
        string input_hash
        float fraud_score
        float anomaly_score
        enum risk_level
        float latency_ms
        string model_version
        datetime created_at
    }
```

### 3.6 Authentication & Authorization Audit

- **Mechanism:** JWT (JSON Web Tokens) with HMAC-SHA256 (`HS256`).
- **Dependencies:** `api/middleware/auth_middleware.py`:
  - `get_current_user`: Validates Bearer token from `Authorization` header, retrieves user from database, verifies active status.
  - `get_current_admin`: Verifies `user.is_admin == True`.
- **Security Assessment:**
  - Password hashing uses bcrypt via Passlib.
  - Token claims contain user UUID as `sub` and user email.
  - Expiration is set to 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES = 60`).
  - *Identified Gaps:* No refresh token mechanism, no token revocation/blacklisting, no rate limiting on `/auth/login` or `/auth/register`.

### 3.7 Frontend: Streamlit Dashboard

- **Entry Point:** `dashboard/app.py`
- **State Management:** Uses `st.session_state` for:
  - `authenticated` (`bool`)
  - `token` (`str`)
  - `user_id`, `user_name`, `user_email` (`str`)
  - `dark_mode` (`bool`)
  - `page` (`str`: `Overview`, `Transactions`, `Alerts`, `Live Predict`, `Behaviour`)
  - `auth_stage` (`None`, `login`, `register`)
- **Theme & CSS System:** Injects CSS variables (`--bg`, `--surface`, `--border`, `--text`, `--muted`, `--accent`, `--card`) into DOM with support for dark/light toggle and custom Plotly templates (`plotly_dark` vs `plotly_white`).
- **Views Implemented:**
  1. `login.py`: Modern landing page with hero, statistics cards, and full authentication forms.
  2. `overview.py`: Executive dashboard with 5 KPI cards, daily transaction trend chart, risk donut chart, monthly combo bar/line chart, fraud score histogram, and recent alerts.
  3. `transactions.py`: Filterable data table with fraud risk highlighting, statistical summary metrics, and CSV export.
  4. `alerts_page.py`: Alert triage list with status update dropdowns (`open`, `reviewed`, `resolved`, `false_positive`), risk filters, and timeline area chart.
  5. `predict_page.py`: Interactive simulation console for credit card fraud (with PCA sliders/randomizers and SHAP visualization) and behavioral anomalies (with risk flags and SVG gauge).
  6. `behavior_page.py`: Behavioral analysis page with session risk distributions, score histograms, country/category charts, and login hour heatmaps.

### 3.8 Redis Usage & Caching Status

- **Configuration:**
  - `requirements.txt`: Includes `redis==5.0.4`.
  - `docker-compose.yml`: Defines `redis:7-alpine` service with port `6379:6379` and volume `redis_data`.
  - `core/config.py`: Includes `redis_url: str = os.getenv("REDIS_URL")`.
- **Actual Implementation Status:** **0% Implemented (Completely Unused)**.
  - Zero imports of `redis` in any service, router, or utility.
  - No caching layer for expensive aggregate queries (`/alerts/stats`).
  - No caching of ML prediction results by input hash.
  - No rate limiting or session store implemented with Redis.

### 3.9 Docker & Infrastructure Configuration

- **`docker-compose.yml` Services:**
  1. `postgres`: PostgreSQL 16 Alpine, exposed on 5432, healthcheck configured with `pg_isready`.
  2. `redis`: Redis 7 Alpine, exposed on 6379, healthcheck configured with `redis-cli ping`.
  3. `api`: FastAPI container built from `docker/Dockerfile.api`, depends on healthy postgres & redis, mounts models and logs volumes.
  4. `dashboard`: Streamlit container built from `docker/Dockerfile.dashboard`, exposed on 8501.
- **`Dockerfile.api`:**
  - Multi-stage build (stage 1: `builder` with `gcc`, `libpq-dev`; stage 2: `python:3.11-slim` runtime with `libpq5`).
- **`Dockerfile.dashboard`:**
  - Builds from `python:3.11-slim`, installs requirements, runs Streamlit with headless flags.
- **Defects Discovered:**
  - `dashboard` container cannot connect to `api` container because `dashboard/api_client.py` does not read `os.getenv("API_BASE")`.

### 3.10 Configuration & Environment Variables

- **`core/config.py`:**
  - Uses `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_file=".env")`.
- **Environment Variables Catalog:**
  | Variable | Default in Code | Purpose |
  | :--- | :--- | :--- |
  | `APP_NAME` | `Detexa` | System branding name |
  | `APP_VERSION` | `1.0.0` | Semantic version string |
  | `APP_ENV` | `development` | Deployment environment (`development` / `production`) |
  | `SECRET_KEY` | `change-me-...` | JWT signing secret |
  | `ALGORITHM` | `HS256` | JWT algorithm |
  | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token expiration time in minutes |
  | `DATABASE_URL` | `os.getenv("DATABASE_URL")` | SQLAlchemy connection string |
  | `REDIS_URL` | `os.getenv("REDIS_URL")` | Redis connection string |
  | `API_HOST` | `0.0.0.0` | API bind host |
  | `API_PORT` | `8000` | API bind port |
  | `CORS_ORIGINS` | `["http://localhost:8501", ...]` | Allowed CORS origins list |
  | `MODEL_PATH` | `ml/models/saved` | Directory holding serialized `.pkl` models |
  | `FRAUD_THRESHOLD` | `0.5` | Threshold for Medium risk & fraud flag |
  | `HIGH_RISK_THRESHOLD`| `0.75` | Threshold for High risk |

### 3.11 Test Suite Audit

- **File:** `tests/test_api.py`
- **Scope:** 10 integration test functions testing `/auth/register`, `/auth/login`, `/auth/me`, `/predict/credit`, `/predict/behavior`, `/alerts/stats`, `/alerts`, and `/health`.
- **Current Limitations:**
  - No unit tests for feature engineering pipelines (`ml/pipelines/feature_engineering.py`).
  - No unit tests for model wrappers (`credit_fraud_model.py`, `behavior_model.py`).
  - No tests for alert status update endpoint (`PUT /alerts/{id}/status`).
  - No tests for transaction listing endpoint (`GET /alerts/transactions`).
  - Test setup sets `os.environ["DATABASE_URL"] = "sqlite:///./test.db"` after settings might already be imported, and SQLAlchemy connection pool arguments in `database/db.py` can conflict with SQLite.

### 3.12 Reusable Utilities Catalog

1. **`core.logging.logger`:** Centralized, thread-safe Loguru logger with pre-configured color console formatter and 10MB auto-rotating file sink (`logs/detexa.log`).
2. **`core.security`:** `hash_password`, `verify_password`, `create_access_token`, `decode_token`.
3. **`ml.models.credit_fraud_model.CreditFraudModel`:** Singleton model inference wrapper with input hashing, schema normalization, and SHAP feature extraction.
4. **`ml.models.behavior_model.BehaviorAnomalyModel`:** Singleton anomaly model inference wrapper with score clamping and risk classification.
5. **`dashboard.views.overview` & `dashboard.views.predict_page`:** SVG score gauge renderer (`_score_gauge`) and KPI card generator (`_kpi`).

---

## 4. Section 3: Discovered Bugs & Architectural Flaws

### 4.1 Critical Severity Flaws

#### 🚨 Bug 1: Missing Auth Header in Dashboard `_post()` Method
- **File:** `dashboard/api_client.py` (lines 38–50)
- **Root Cause:**
  ```python
  def _post(path: str, body: Dict) -> Any:
      try:
          r = requests.post(f"{API_BASE}{path}", json=body, timeout=TIMEOUT) # Missing headers=_headers()!
  ```
- **Impact:** While `_get()` and `_put()` send `headers=_headers()`, `_post()` does not send the authorization header. The API endpoints `POST /predict/credit` and `POST /predict/behavior` require authentication via `get_current_user`. When users attempt to run live predictions from the dashboard, the requests fail with `401 Unauthorized`.
- **Resolution:** Modify `_post(path: str, body: Dict, auth: bool = False)` or pass `headers=_headers()` for non-login/register endpoints.

---

#### 🚨 Bug 2: Hardcoded API Base URL in Dashboard Client Breaks Docker Networking
- **File:** `dashboard/api_client.py` (line 13)
- **Root Cause:**
  ```python
  API_BASE = "http://localhost:8000/api/v1"
  ```
- **Impact:** In `docker-compose.yml`, the environment variable `API_BASE: http://api:8000/api/v1` is passed to the dashboard container. Because `api_client.py` hardcodes the localhost URL instead of reading `os.getenv("API_BASE", "http://localhost:8000/api/v1")`, the dashboard container cannot reach the backend API container when deployed with Docker.
- **Resolution:** Change line 13 to:
  ```python
  import os
  API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")
  ```

---

#### 🚨 Bug 3: SHAP Feature Explanations Return Generic Feature Names (`f0`, `f1`...)
- **File:** `ml/pipelines/feature_engineering.py` (lines 68–71) & `ml/models/credit_fraud_model.py` (lines 126–128)
- **Root Cause:** In `CreditFeatureEngineer`, `_feature_names_cache` is never set during `fit()` or `transform()`. When `CreditFraudModel._explain()` accesses `getattr(self._pipeline.named_steps["features"], "_feature_names_cache", [f"f{i}" for i in range(len(values))])`, it always falls back to the default list of `f0`, `f1`, `f2`... instead of showing the actual feature names (`V14`, `Amount`, `V1_V2_interaction`, `v_norm`, etc.).
- **Impact:** SHAP explanations in the API response and dashboard UI display unhelpful labels like `f12 -> +0.3421` instead of `V14 -> +0.3421`.
- **Resolution:** Save `self._feature_names_cache = self._feature_names(df)` inside `CreditFeatureEngineer.fit()` and `CreditFeatureEngineer.transform()`.

---

### 4.2 Major Severity Flaws

#### ⚠️ Bug 4: Inconsistent Default Values in Pydantic Settings
- **File:** `core/config.py` (lines 34, 37)
- **Root Cause:**
  ```python
  database_url: str = os.getenv("DATABASE_URL")
  redis_url: str = os.getenv("REDIS_URL")
  ```
- **Impact:** Using `os.getenv()` at class definition time bypasses Pydantic-Settings' built-in `.env` file resolution. If environment variables are not already set in `os.environ` before Python imports `core.config`, these fields initialize to `None` instead of reading from `.env` or using proper default fallback connection strings.
- **Resolution:** Define fields as:
  ```python
  database_url: str = "postgresql://detexa_user:detexa_pass@localhost:5432/detexa_db"
  redis_url: str = "redis://localhost:6379/0"
  ```

---

#### ⚠️ Bug 5: Complete Omission of Redis Implementation
- **Files:** Entire `services/` and `api/` directories
- **Root Cause:** Redis is listed as a dependency, containerized in `docker-compose.yml`, and configured in `.env`, but no client code connects to Redis or leverages it.
- **Impact:** High-load endpoints (`/alerts/stats`, repeated predictions for identical payloads) perform unnecessary database aggregates and redundant model inferences, causing unnecessary latency and resource utilization.
- **Resolution:** Implement a Redis cache service/decorator for dashboard statistics and cached prediction lookups.

---

### 4.3 Moderate & Minor Severity Flaws

#### 🔍 Bug 6: Malformed Token Subject Triggers Unhandled 500 Error
- **File:** `api/middleware/auth_middleware.py` (line 41)
- **Root Cause:** `UUID(user_id)` is called directly without a `try...except ValueError` block.
- **Impact:** If an invalid or non-UUID token is presented, FastAPI raises an unhandled 500 Internal Server Error instead of a clean 401 Unauthorized response.
- **Resolution:** Wrap UUID parsing in `try...except (ValueError, TypeError)` and raise `credentials_exception`.

---

#### 🔍 Bug 7: Behavior Analytics Page Samples Alerts Instead of Behavior Logs
- **File:** `dashboard/views/behavior_page.py` (lines 27–28)
- **Root Cause:** `behavior_page.py` queries `get_alerts()` and filters for `alert_type == "behavior_anomaly"` because there is no `GET /api/v1/behavior/logs` endpoint.
- **Impact:** Normal (non-anomalous) user behavior logs are never fetched or displayed. The behavior analytics charts only reflect sessions that were flagged as alerts, skewing all distributions and charts.
- **Resolution:** Create a dedicated `GET /api/v1/behavior/logs` API endpoint and update `behavior_page.py` to query it.

---

#### 🔍 Bug 8: Missing Alembic Version Migration Scripts
- **File:** `alembic/`
- **Root Cause:** `alembic/versions` directory does not exist, and no initial migration revision has been generated. The application relies entirely on `Base.metadata.create_all(bind=engine)` during FastAPI startup.
- **Impact:** Schema migrations in production cannot be safely managed, rolled back, or audited without Alembic migration revisions.
- **Resolution:** Generate an initial Alembic migration (`alembic revision --autogenerate -m "Initial schema"`).

---

#### 🔍 Bug 9: Database Connection Pool Parameters Cause Issues with SQLite in Tests
- **File:** `database/db.py` (lines 12–18)
- **Root Cause:** `pool_size=10` and `max_overflow=20` are passed to `create_engine()` unconditionally.
- **Impact:** When SQLite is used for unit tests (`sqlite:///...`), SQLite's `NullPool` or `SingletonThreadPool` rejects `pool_size` / `max_overflow` arguments in certain SQLAlchemy configurations.
- **Resolution:** Conditionally apply connection pool parameters only when `settings.database_url` is PostgreSQL.

---

## 5. Section 4: Missing Functionality Report

### 5.1 API & Backend Gaps
- [ ] **Dedicated Transaction Management Endpoints:** Currently, transactions are only queryable via `/alerts/transactions`. There is no dedicated `/transactions` router with single-transaction detail (`GET /transactions/{id}`), transaction creation, or search/filtering by amount range and date range.
- [ ] **Dedicated Behavior Logs API:** No `GET /api/v1/behavior/logs` or `GET /api/v1/behavior/logs/{id}` endpoints exist.
- [ ] **User & Role Management API:** No admin endpoints to list users (`GET /users`), deactivate accounts (`PUT /users/{id}/status`), or promote users to admin (`PUT /users/{id}/role`).
- [ ] **Batch Prediction Endpoints:** No batch inference endpoints (`POST /predict/credit/batch`, `POST /predict/behavior/batch`) for processing CSV uploads or bulk transaction streams.
- [ ] **API Rate Limiting:** No rate limiting middleware on public auth endpoints (`/auth/login`, `/auth/register`) or inference endpoints.

### 5.2 Machine Learning & Explainability Gaps
- [ ] **Dynamic Feature Names in Feature Engineer:** Feature engineer should automatically retain input column mappings for arbitrary feature sets.
- [ ] **Model Drift & Performance Tracking:** No endpoint or service to log ground-truth labels after chargebacks and compute live AUC-ROC / precision-recall metrics.
- [ ] **Model Retraining Pipeline:** No automated retraining trigger or API endpoint (`POST /ml/retrain`).
- [ ] **SHAP Waterfall / Force Plot Visualization:** Frontend only displays text values for SHAP feature contributions rather than visual bar charts or waterfall plots.

### 5.3 Frontend Dashboard Gaps
- [ ] **Live Webhook / Real-Time Alert Polling:** Dashboard requires manual refresh or action triggers; no auto-refresh or WebSocket stream for incoming high-risk alerts.
- [ ] **CSV Batch Upload UI:** No interface in `predict_page.py` for uploading a CSV of transactions and viewing batch prediction scores and downloadable results.
- [ ] **User Management View:** No admin page in the dashboard to view users, inspect activity, or toggle administrator privileges.
- [ ] **Transaction Detail Modal:** Clicking a transaction in `transactions.py` does not open a comprehensive detail drawer or view showing its corresponding SHAP explanations and triggered alert details.

### 5.4 Database, Migration & Caching Gaps
- [ ] **Redis Caching Layer:** Caching for dashboard aggregate metrics (`/alerts/stats` with a 30s TTL) and idempotent prediction caching.
- [ ] **Alembic Version History:** Version migration files under `alembic/versions/`.
- [ ] **Database Indexes Optimization:** Additional composite indexes on `transactions(user_id, timestamp)` and `alerts(status, risk_level, created_at)`.

### 5.5 Security & Production Readiness Gaps
- [ ] **Token Refresh & Revocation:** Refresh token exchange endpoint (`POST /auth/refresh`) and token blacklist via Redis.
- [ ] **Production Health & Metrics Endpoints:** Detailed health check inspecting Database and Redis connectivity (`/health/ready`, `/health/live`) and Prometheus metrics exposition (`/metrics`).
- [ ] **Password Strength Validation:** Regex enforcement for password complexity on registration.

---

## 6. Section 5: Recommended Implementation Order & Roadmap

To resolve all identified bugs and complete the platform systematically, the following phased implementation sequence is recommended:

```mermaid
flowchart LR
    P1["Phase 1<br/>Critical Bug Fixes<br/>& Core Stability"]
    P2["Phase 2<br/>Database, Migrations<br/>& Redis Integration"]
    P3["Phase 3<br/>ML Pipelines &<br/>SHAP Enhancements"]
    P4["Phase 4<br/>API Expansion &<br/>New Endpoints"]
    P5["Phase 5<br/>Dashboard Enhancements<br/>& Batch UI"]
    P6["Phase 6<br/>Test Suite Expansion<br/>& Production Hardening"]

    P1 --> P2 --> P3 --> P4 --> P5 --> P6
```

### Phase 1: Critical Bug Fixes & Core Stability (Immediate Priority)
1. **Fix `dashboard/api_client.py` Auth Header:** Add `headers=_headers()` to `_post()` so all authenticated POST endpoints (`/predict/credit`, `/predict/behavior`) function from the dashboard.
2. **Fix `dashboard/api_client.py` Docker URL:** Read `API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")`.
3. **Fix `CreditFeatureEngineer` Feature Names:** Cache transformed feature column names in `_feature_names_cache` to restore clear SHAP feature labels in predictions.
4. **Fix `core/config.py` Defaults:** Replace `os.getenv()` with standard Pydantic defaults and fallback connection strings.
5. **Fix `auth_middleware.py` UUID Parsing:** Add exception handling for invalid UUIDs in JWT claims.
6. **Fix `database/db.py` SQLite Compatibility:** Ensure connection pooling arguments are only passed when using PostgreSQL.

### Phase 2: Database, Migrations & Redis Integration
1. **Initialize Alembic Migrations:** Create `alembic/versions/` and generate the initial baseline migration revision.
2. **Implement Redis Client & Service:** Create `core/redis.py` to establish connection pooling with Redis.
3. **Implement Redis Caching:** Cache `/alerts/stats` responses with automatic invalidation when new transactions or alerts are created.
4. **Implement Prediction Deduplication Cache:** Cache predictions in Redis using the payload's SHA-256 hash.

### Phase 3: ML Pipeline & Explainability Enhancements
1. **Refactor Feature Pipeline:** Standardize feature naming and ensure seamless serialization between training and runtime.
2. **Enhance SHAP Explanations:** Return formatted feature descriptions, baseline expected values, and relative impact percentages.
3. **Add Retraining Routine:** Ensure `scripts/train_models.py` can be triggered programmatically and safely reloads singleton model instances.

### Phase 4: API Expansion & New Endpoints
1. **Create Dedicated Transactions Router (`api/routers/transactions.py`):**
   - `GET /api/v1/transactions` (with date range, amount range, merchant search, and pagination).
   - `GET /api/v1/transactions/{id}` (returns transaction details, associated alerts, and SHAP values).
2. **Create Behavior Logs Router (`api/routers/behavior.py`):**
   - `GET /api/v1/behavior/logs` (paginated list of raw session logs).
   - `GET /api/v1/behavior/stats` (session anomaly statistics).
3. **Create Batch Prediction Endpoints:**
   - `POST /api/v1/predict/credit/batch` (accepts array of transactions or CSV upload).
4. **Create Admin User Management Router (`api/routers/users.py`):**
   - `GET /api/v1/users`, `PUT /api/v1/users/{id}/status`, `PUT /api/v1/users/{id}/role`.

### Phase 5: Dashboard Enhancements & UI Features
1. **Update `behavior_page.py`:** Switch data source from alerts to the new `/behavior/logs` endpoint for true behavioral analytics.
2. **Add Batch Upload Tab in `predict_page.py`:** Enable drag-and-drop CSV prediction with instant batch scoring, summary charts, and CSV download.
3. **Add Transaction Detail Modal / Drawer:** Provide deep-dive inspection of any transaction row in `transactions.py`.
4. **Add Interactive SHAP Plot:** Render horizontal bar chart of feature contributions in `predict_page.py`.
5. **Add Auto-Refresh / Polling Toggle:** Allow live monitoring on the `overview.py` and `alerts_page.py` pages.

### Phase 6: Test Suite Expansion & Production Hardening
1. **Unit Tests for Feature Engineering & Models:** Write tests verifying `CreditFeatureEngineer`, `BehaviorFeatureEngineer`, `CreditFraudModel`, and `BehaviorAnomalyModel`.
2. **Unit Tests for All Routers & Services:** Expand `tests/test_api.py` to test alerts status updating, transaction filtering, error states, and admin authorization.
3. **Readiness & Liveness Endpoints:** Implement `/health/ready` (testing DB & Redis ping) and `/health/live`.
4. **Docker Compose & Production Validation:** Verify full-stack deployment with `docker compose up --build`.

---
*Report compiled and saved to `docs/INSPECTION_REPORT.md`.*
