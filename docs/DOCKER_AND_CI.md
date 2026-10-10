# 🐳 Detexa Docker Architecture, Dependency Management & CI/CD Guide

This document details the production-ready Docker Compose architecture, dependency isolation strategies, layer caching optimizations, and the GitHub Actions CI/CD pipeline for Detexa.

---

## 🏗️ 1. Architecture Overview & Services

Detexa uses a single-command multi-container Docker Compose setup (`compose.yaml` / `docker-compose.yml`) coordinating real-time streaming, in-memory feature stores, ML inference, and analytical dashboarding.

```
                      ┌─────────────────────────────────┐
                      │   detexa_frontend (Nginx SPA)   │ :5173
                      └────────────────┬────────────────┘
                                       │ (REST / SSE / WS)
                                       ▼
                      ┌─────────────────────────────────┐
                      │    detexa_backend (FastAPI)     │ :8000
                      └──────┬──────────────┬───────────┘
                             │              │
                ┌────────────┴──┐      ┌────┴────────────┐
                ▼               ▼      ▼                 ▼
        ┌──────────────┐ ┌──────────┐ ┌────────────────┐ ┌─────────────────┐
        │ detexa_redis │ │  detexa  │ │   Neon Cloud   │ │ detexa_db_      │
        │ Feature Store│ │  _kafka  │ │   PostgreSQL   │ │ migrate         │
        │ :6379        │ │ :9092    │ │   (External)   │ │ (One-shot)      │
        └──────┬───────┘ └────┬─────┘ └────────────────┘ └─────────────────┘
               │              │
               │         ┌────┴───────────────────────────┐
               │         ▼                                ▼
        ┌──────┴────────────────┐              ┌──────────────────────┐
        │  detexa_flink_worker  │              │  Flink JobManager    │ :8081
        │ (Kafka Stream Engine) │              │  & TaskManager Slots │
        └───────────────────────┘              └──────────────────────┘
```

### Container Roster & Responsibilities

| Service | Image / Base | Ports | Healthcheck | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`detexa_redis`** | `redis:7.2-alpine` | `6379:6379` | `redis-cli ping` | Sub-millisecond feature store, user velocity tracking, and entity graph index sets. |
| **`detexa_kafka`** | `confluentinc/cp-kafka:7.6.0` | `9092:9092`, `29092:29092` | `kafka-cluster cluster-id` | Distributed event streaming broker running in lightweight KRaft mode (no Zookeeper). |
| **`detexa_flink_jobmanager`** | `flink:1.18-scala_2.12-java11` | `8081:8081` | Web UI `:8081` | Apache Flink distributed cluster coordinator. |
| **`detexa_flink_taskmanager`** | `flink:1.18-scala_2.12-java11` | Internal | Flink RPC | Apache Flink distributed processing slots (4 parallel task slots). |
| **`detexa_db_migrate`** | Custom Python Multi-Stage | None (One-shot) | None | Executes `alembic upgrade head` before backend startup. Exits with code 0 on success. |
| **`detexa_backend`** | Custom Python Multi-Stage | `8000:8000` | `GET /health` | FastAPI REST endpoints, real-time ML inference (XGBoost, SHAP, Isolation Forest), WS/SSE. |
| **`detexa_flink_worker`** | Custom Python Multi-Stage | Internal | Internal | High-throughput Kafka stream processor with sliding-window aggregators. |
| **`detexa_frontend`** | `nginx:1.27-alpine` Multi-Stage| `5173:80` | `GET /health` | Production-optimized React SPA served with gzip, security headers, and API proxying. |
| **`detexa_postgres_local`** *(Optional)* | `postgres:16-alpine` | `5432:5432` | `pg_isready` | Optional local database profile (`--profile local-db`) when offline from Neon Cloud. |

---

## ⚡ 2. Dependency Isolation & Optimization Matrix

To minimize image build duration, eliminate bloat, and prevent security vulnerabilities, dependencies are strictly separated into dedicated files:

```
backend/
├── requirements.txt         # Core FastAPI runtime + ML inference (XGBoost, SHAP, Scikit-learn, SQLAlchemy, etc.)
├── requirements-worker.txt  # Dedicated Flink worker stream processing runtime (no web/auth/dev packages)
└── requirements-dev.txt     # Test runners (pytest, pytest-cov, faker, imbalanced-learn)
```

### Dependency Audit & Removal

1. **Removed Neo4j (`neo4j` package & container):**
   - Architectural audit confirmed graph entity link queries (`shared_device_users`, `shared_ip_users`) are executed with sub-millisecond latency via Redis sets (`device:{device_fp}:users`) and PostgreSQL relational queries.
   - Saves ~1.2 GB container memory overhead, ~45s boot time, and removes Python driver bloat.
2. **Removed Dev/Test Packages from Runtime (`requirements-dev.txt`):**
   - `pytest`, `pytest-asyncio`, `pytest-cov`, `faker`, and `imbalanced-learn` are excluded from production container builds.
3. **Dedicated Worker Requirements (`requirements-worker.txt`):**
   - The Flink streaming worker does not import FastAPI, Uvicorn, Jose, Bcrypt, SHAP, or Groq. Installing only Kafka, Redis, Pandas, NumPy, and XGBoost saves ~40% build time for the worker image.
4. **Precompiled Wheels & No Compilers:**
   - Multi-stage Docker builds install wheels into `/install` in the builder stage using precompiled Linux binaries (`manylinux`), eliminating `build-essential`, `gcc`, and header files in the final runtime images.

---

## 🚀 3. Single-Command Startup & Operational Workflows

### Default Setup (Cloud Neon PostgreSQL)

1. Configure your environment:
   ```bash
   cp .env.example .env
   ```
2. Set your `DATABASE_URL` in `.env`:
   ```ini
   DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/detexa?sslmode=require
   ```
3. Start the entire platform with one command:
   ```bash
   docker compose up --build -d
   ```
4. Check running services:
   ```bash
   docker compose ps
   ```

### Fully Local Setup (Offline Local PostgreSQL)

When working offline or testing locally without a remote Neon instance:

```bash
docker compose --profile local-db up --build -d
```

Override `DATABASE_URL` to point to the local service:
```ini
DATABASE_URL=postgresql://detexa:detexa_local_password@postgres-local:5432/detexa
```

---

## 🔍 4. Verification, Healthchecks & Smoke Testing

### 1. Health Endpoints
- **Backend API:** `curl -s http://localhost:8000/health`
  ```json
  {"status":"healthy","database":"connected","redis":"connected","kafka":"connected","models_loaded":["xgboost_fraud","isolation_forest"]}
  ```
- **Frontend Nginx:** `curl -s http://localhost:5173/health`
  ```
  healthy
  ```
- **Flink Dashboard:** Open `http://localhost:8081` in your browser.

### 2. Live Transaction Prediction Smoke Test
```bash
curl -X POST http://localhost:8000/api/v1/predict/realtime \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 4999.00,
    "user_id": "usr_test_01",
    "device_fingerprint": "dev_fp_98231",
    "ip_address": "198.51.100.4",
    "merchant_id": "merch_electronics_01",
    "channel": "ONLINE",
    "country": "US"
  }'
```

### 3. Run Integration Test Suite Inside Container
```bash
docker exec detexa_backend pytest tests/unit tests/api -v
```

### 4. Clean Teardown
```bash
docker compose down -v
```

---

## 🤖 5. GitHub Actions CI/CD Pipeline

The automated CI workflow is configured in [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml). It validates the codebase across 4 distinct jobs:

```
                                  GitHub Actions CI
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
        │  Backend Checks  │    │ Frontend Checks  │    │ Docker Validation│
        │  (Python 3.11)   │    │   (Node.js 20)   │    │ (Compose Build)  │
        │  - Syntax & Lint │    │  - npm ci        │    │  - Buildx cache  │
        │  - Pytest Suite  │    │  - Typecheck     │    │  - Multi-image   │
        └─────────┬────────┘    │  - Vite Build    │    └──────────────────┘
                  │             └──────────────────┘
                  ▼
        ┌──────────────────┐
        │Integration Checks│
        │ (Postgres/Redis) │
        │  - Alembic Head  │
        │  - E2E Predict   │
        └──────────────────┘
```

### Pipeline Jobs Breakdown

1. **`backend-checks`:**
   - Sets up Python 3.11 with pip caching.
   - Installs `requirements-dev.txt`.
   - Executes syntax validation and unit test suites (`pytest backend/tests/unit backend/tests/api`).
2. **`frontend-checks`:**
   - Sets up Node.js 20 with npm caching.
   - Runs `npm ci` and verifies TypeScript compilation.
   - Executes `npm run build` to ensure production bundle integrity.
3. **`docker-validation`:**
   - Uses `docker/setup-buildx-action` and GitHub Actions Docker layer caching (`type=gha`).
   - Validates `docker compose config`.
   - Builds all Docker images (`backend`, `flink-worker`, `frontend`).
4. **`integration-checks`:**
   - Spins up real isolated `postgres:16-alpine` and `redis:7.2-alpine` service containers in GitHub Actions.
   - Runs `alembic upgrade head` to verify database migration idempotency.
   - Executes end-to-end integration and prediction tests against real services (no production credentials).

---

## 🛡️ 6. Environment & Security Best Practices

- **Zero Baked Credentials:** Dockerfiles and images do not contain `.env` files, API keys, or database credentials.
- **Fail-Fast Validation:** The FastAPI backend validates all required configurations on boot (`core/config.py`) and fails immediately with actionable diagnostics if required variables are missing.
- **Dedicated Migration Runner:** Concurrent backend replicas do not run database migrations simultaneously. `detexa_db_migrate` executes migrations once during stack startup before the API container boots.
- **Safe Placeholders:** All repository environment templates (`.env.example`) use safe sanitized dummy strings.
