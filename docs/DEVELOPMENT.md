# Detexa Developer Guide

This guide covers local development workflows, environment configuration, database migrations, model training/retraining pipelines, Docker orchestration, and debugging techniques for the Detexa platform.

---

## 1. Prerequisites

Ensure the following tools are installed on your workstation:
- **Docker & Docker Compose:** Docker Engine 24.0+ / Docker Compose v2.20+
- **Python:** Version 3.11.x
- **Node.js & npm:** Node 18.x or 20.x, npm 9.x+
- **Git:** Version 2.30+

---

## 2. Environment Configuration (`.env`)

Detexa uses a single unified `.env` file at the repository root. Ensure the file contains:

```env
# Application Settings
APP_NAME=Detexa
APP_ENV=development
APP_VERSION=2.0.0
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production-min-32-chars-long
API_V1_STR=/api/v1
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]

# PostgreSQL / Neon Database
DATABASE_URL=postgresql://neondb_owner:npg_Xk0yI6rUeLms@ep-ancient-sky-a87l140z-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis Feature Store
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_ENABLED=True

# Apache Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_ENABLED=True
KAFKA_TOPIC_TRANSACTIONS=transactions.raw
KAFKA_TOPIC_ALERTS=fraud.alerts
KAFKA_TOPIC_METRICS=metrics.stream

# Neo4j Graph Database
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=detexa_secret_password
NEO4J_ENABLED=True

# Decision Engine Policy Thresholds
THRESHOLD_ALLOW=0.30
THRESHOLD_CHALLENGE=0.70
THRESHOLD_REVIEW=0.90
THRESHOLD_BLOCK=0.90

# ML Model Paths
CREDIT_MODEL_PATH=models/credit_fraud_xgboost.joblib
CREDIT_SCALER_PATH=models/credit_fraud_scaler.joblib
BEHAVIOR_MODEL_PATH=models/behavior_isolation_forest.joblib
BEHAVIOR_SCALER_PATH=models/behavior_scaler.joblib
```

> **Note:** When running the backend directly on your host machine (outside Docker), update container hostnames (`redis`, `kafka`, `neo4j`) to `localhost` and use host-mapped ports (`localhost:6379`, `localhost:9094`, `localhost:7687`).

---

## 3. Docker Workflows

### 3.1 Start Stack
```bash
# Build and start all services in detached mode
docker compose up --build -d
```

### 3.2 View Logs
```bash
# Follow logs for all services
docker compose logs -f

# Follow specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f kafka
```

### 3.3 Check Status & Health
```bash
docker compose ps
```

### 3.4 Stop Stack
```bash
# Stop containers (preserves volume data)
docker compose down

# Stop containers and remove volumes (clean slate)
docker compose down -v
```

---

## 4. Local Backend Development

To run the backend on the host machine without Docker:

### 4.1 Setup Virtual Environment
```bash
cd backend
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4.2 Start Supporting Services
Run only supporting storage and streaming infrastructure via Docker:
```bash
docker compose up -d redis kafka neo4j zookeeper
```

### 4.3 Run Database Migrations
```bash
cd backend
alembic upgrade head
```

### 4.4 Start FastAPI Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger UI will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 5. Local Frontend Development

### 5.1 Install Dependencies
```bash
cd frontend
npm install
```

### 5.2 Start Vite Dev Server
```bash
npm run dev
```
The React development server runs at [http://localhost:5173](http://localhost:5173).

### 5.3 Production Build & Typecheck
```bash
npm run build
```
Runs `tsc` (TypeScript compiler) followed by `vite build`.

---

## 6. Database Migrations (Alembic)

All schema changes are version-controlled via Alembic in `backend/alembic/`.

### 6.1 Apply Latest Migrations
```bash
cd backend
alembic upgrade head
```

### 6.2 Create a New Migration
When modifying SQLAlchemy models in `backend/app/models/`:
```bash
cd backend
alembic revision --autogenerate -m "describe_schema_change"
```

### 6.3 Roll Back a Migration
```bash
cd backend
alembic downgrade -1
```

> **Important:** The Docker backend container entrypoint automatically executes `alembic upgrade head` on startup before launching FastAPI.

---

## 7. Dataset Placement & Model Training

### 7.1 Dataset Placement
Detexa utilizes the Indian banking transaction dataset: `indian_banking_transactions.csv`.

1. Download the transaction dataset from Kaggle.
2. Ensure directory `backend/data/raw/` exists:
   ```bash
   mkdir -p backend/data/raw
   ```
3. Place the CSV file at:
   ```text
   backend/data/raw/indian_banking_transactions.csv
   ```

### 7.2 Train Indian Banking Fraud Model (XGBoost)
To train and export new model artifacts:
```bash
python backend/scripts/train_banking_fraud_model.py
```
This generates:
- `backend/app/ml/saved/banking_fraud_pipeline.pkl` (Trained pipeline)
- `backend/app/ml/saved/banking_fraud_pipeline_metadata.json` (Pipeline metadata)
- `backend/app/ml/saved/feature_metadata.json` (Feature schema)

### 7.3 Train Behavioral Anomaly Model (Isolation Forest)
```bash
cd backend
python -m app.ml.train_behavior_model
```
This generates:
- `backend/models/behavior_isolation_forest.joblib`
- `backend/models/behavior_scaler.joblib`

---

## 8. Adding or Changing Features in Canonical Schema

When adding new features to the 61-feature canonical vector:
1. **Schema Definition:** Update `backend/app/services/feature_service.py` to register the new feature name under its respective group (`transaction`, `temporal`, `behavioral`, `redis_hot`, `graph_risk`).
2. **Feature Extractor:** Implement feature extraction logic in `backend/app/ml/feature_pipeline.py`.
3. **Model Retraining:** Re-fit the scaler and booster using `app.ml.train_credit_model`.
4. **Frontend Alignment:** Verify that feature descriptions and charts in `ModelStatisticsPage.tsx` reflect the updated schema count.

---

## 9. Troubleshooting & Debugging

| Issue | Cause | Resolution |
|---|---|---|
| `NoBrokersAvailable` | Backend cannot connect to Kafka | Ensure `KAFKA_BOOTSTRAP_SERVERS` is set to `kafka:9092` (inside Docker) or `localhost:9094` (on host). |
| `DuplicateObject: type "risklevel" already exists` | Alembic enum collision in PostgreSQL | Safe enum check is implemented in `0001_initial_neon_schema.py`. Ensure migration is executed via `alembic upgrade head`. |
| `Redis Connection Refused` | Redis container not running | Check `docker compose ps` and verify port `6379`. |
| `Neo4j Unauthorized` | Password mismatch | Verify `NEO4J_PASSWORD` in `.env` matches container initialization credentials (`detexa_secret_password`). |
| `Theme Flashing on Reload` | Theme script not executing in `<head>` | Verify `index.html` inline script checks `localStorage.getItem('detexa_theme')` before body render. |

---

## 10. Platform Validation & Benchmark Suite

This section outlines the exact test procedures, commands, execution environments, sample sizes, and empirically measured results across all validation domains.

### 10.1 Test Execution Environment
- **Operating System:** Windows 10 Host with WSL2 / Docker Linux Containers
- **CPU:** Intel Core Processor (16 logical cores)
- **RAM:** 15.65 GB System Memory
- **Python Version:** Python 3.11.x (Docker backend) / Python 3.10.9 (Host CLI)
- **Docker Stack:** Redis 7-Alpine, Neo4j 5.18.0, Apache Kafka 3.7.0 (KRaft), Apache Flink 1.18.1 (JobManager & TaskManager)

---

### 10.2 Validation Procedures & Measured Results

#### 1. Baseline Unit & Integration Tests (Pytest)
- **Command:** `docker exec detexa_backend pytest tests/ -v`
- **Scope:** Unit, API, Database, Graph, and Streaming E2E suites.
- **Measured Result:** **100% Pass Rate** (0 failures, 0 regressions).

#### 2. Postman Functional API Testing (Newman)
- **Command:** `npx --yes newman run postman/Detexa.postman_collection.json -e postman/Detexa.postman_environment.json`
- **Scope:** Authentication (register, login, token refresh, unauthorized rejection), Health/Readiness, Dashboard summaries, Single/Batch Predictions, Streaming Ingestion, Alert triage.
- **Measured Result:** **12/12 requests executed, 14/14 assertions passed, 0 failures**.

#### 3. Machine Learning Evaluation (Indian Banking Dataset)
- **Command:** `python backend/scripts/evaluate_models.py`
- **Dataset:** `backend/data/raw/indian_banking_transactions.csv` (550,000 total records).
- **Split Protocol:** Strictly time-based chronological split:
  - **Train Set:** 440,000 transactions (2019-01-01 to 2022-12-31).
  - **Holdout Test Set:** 110,000 transactions (2022-12-31 to 2024-01-01), containing **987 positive fraud cases** (0.897% prevalence).
- **Data Leakage Audit:** **PASSED**. No target features present, maximum feature-to-target correlation is 0.0642 (`transaction_amount`), zero temporal split overlap.
- **Comparative Results:**
  - **ROC-AUC:** **0.8156** (XGBoost) vs **0.5474** (Logistic Regression baseline).
  - **PR-AUC:** **0.1041** (XGBoost) vs **0.0170** (Logistic Regression baseline).
  - **Recall @ 1% FPR:** **21.18%** (XGBoost at cutoff 0.6105) vs **8.51%** (Logistic Regression).
  - **Threshold 0.60 Performance:**
    - *XGBoost:* Precision: 0.1614, Recall: 0.2330, F1: 0.1907, Specificity: 0.9890, FPR: 0.0110, FNR: 0.7670. Confusion Matrix: `[[107818, 1195], [757, 230]]`.
    - *Logistic Regression:* Precision: 0.0352, Recall: 0.1145, F1: 0.0539, Specificity: 0.9716, FPR: 0.0284, FNR: 0.8855. Confusion Matrix: `[[105917, 3096], [874, 113]]`.
  - **Threshold 0.85 Performance:**
    - *XGBoost:* Precision: 0.1492, Recall: 0.0719, F1: 0.0971, Specificity: 0.9963, FPR: 0.0037, FNR: 0.9281. Confusion Matrix: `[[108608, 405], [916, 71]]`.
    - *Logistic Regression:* Precision: 0.0643, Recall: 0.0395, F1: 0.0489, Specificity: 0.9948, FPR: 0.0052, FNR: 0.9605. Confusion Matrix: `[[108447, 566], [948, 39]]`.

#### 4. API Real-Time Latency Benchmark (`/api/v1/predict/realtime`)
- **Command:** `python backend/scripts/benchmark_api_latency.py`
- **Setup:** 300 warmup requests (excluded), 1,000 measured requests per trial, 3 trials per concurrency tier with Redis auth session caching (60s TTL).
- **Measured Metrics (Median Trial):**
  - **Concurrency 1:** Throughput: **14.0 req/s**, p50: **65.36 ms**, p95: **128.09 ms**, p99: **188.67 ms**, Errors: 0.
  - **Concurrency 10:** Throughput: **19.2 req/s**, p50: **470.79 ms**, p95: **1006.48 ms**, p99: **1620.93 ms**, Errors: 0.
  - **Concurrency 50:** Throughput: **22.1 req/s**, p50: **2021.46 ms**, p95: **5637.84 ms**, p99: **7723.70 ms**, Errors: 33.

#### 5. Decision Engine Policy Rules & Boundary Verification
- **Command:** `pytest backend/tests/unit/test_decision_engine.py -v`
- **Scope:** 22 unit tests covering >=5 distinct cases each for `ALLOW`, `CHALLENGE`, `REVIEW`, `BLOCK`, and exact boundary conditions around thresholds 0.40, 0.60, 0.65, and 0.85.
- **Measured Result:** **22/22 tests PASSED (100%)**.

#### 6. End-to-End Streaming Pipeline Benchmark
- **Command:** `python backend/scripts/benchmark_streaming_pipeline.py`
- **Pipeline:** API (`POST /api/v1/streaming/transactions`) → Kafka `detexa.transactions.raw` → Flink Worker → Redis/Neo4j → XGBoost → SHAP → Decision Engine → PostgreSQL → WebSocket.
- **Scale:** **10,000 transactions** across 4 progressive concurrency tiers (C=10, 25, 50, 100).
- **Flink Cluster:** Apache Flink 1.18.1 online at `localhost:8081` (1 TaskManager, 4 task slots).
- **Measured Results:**
  - **Total Sent:** 10,000 | **Unique References:** 10,000 | **Duplicate Decisions:** 0.
  - **Delivery Success Rate:** **99.99%** (9,999 / 10,000 processed).
  - **Tier-1 (500 txns @ C=10):** 50.38 req/s, p50: 58.02 ms, p95: 210.99 ms, p99: 6108.17 ms, 0 errors.
  - **Tier-2 (1500 txns @ C=25):** **149.59 req/s**, p50: 99.75 ms, p95: 542.65 ms, p99: 852.58 ms, 0 errors (Peak Zero-Loss Throughput).
  - **Tier-3 (3000 txns @ C=50):** 89.66 req/s, p50: 381.30 ms, p95: 1572.81 ms, p99: 2661.23 ms, 0 errors.
  - **Tier-4 (5000 txns @ C=100):** 72.82 req/s, p50: 808.25 ms, p95: 4484.18 ms, p99: 6605.77 ms, 1 error (0.02% error rate under peak saturation).

#### 7. Infrastructure Resilience & Fault Injection Suite
- **Command:** `python backend/scripts/test_resilience.py`
- **Fault Scenarios:** Stopping and restarting Redis, Neo4j, and Kafka containers (3 iterations each).
- **Fail-Safe Invariant:** System degrades gracefully during outages using fallback buffers and default safe features without crashing, and auto-recovers immediately upon container restart.
- **Measured Result:** **9/9 trials PASSED (100.00% Graceful Recovery Rate)**:
  - Redis Outage (3/3 passed)
  - Neo4j Outage (3/3 passed)
  - Kafka Outage (3/3 passed)

