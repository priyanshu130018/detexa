# 🛡️ Detexa – Real-Time Banking Fraud Detection Platform

Detexa is an enterprise-grade, real-time banking fraud detection and risk scoring platform. It combines distributed event streaming, stateful stream processing, graph-based relationship intelligence, in-memory feature stores, and explainable machine learning models to intercept fraudulent financial transactions with sub-35ms latency.

---

## 🏛️ System Architecture

```
                                  DETEXA PLATFORM ARCHITECTURE

  ┌──────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
  │   React + Vite   │ <───> │ FastAPI Backend │ ────> │  Apache Kafka Broker   │
  │ Frontend (Nginx) │ (SSE) │  REST & WS Hub  │       │ (detexa.transactions)  │
  └──────────────────┘       └─────────────────┘       └───────────┬────────────┘
           ▲                          │                            │
           │                          ▼                            ▼
           │                 ┌─────────────────┐       ┌────────────────────────┐
           │ (REST / Auth)   │  Redis Feature  │       │ Apache Flink Processor │
           │                 │ Store & Sets    │ <───> │   (Windowed Velocity)  │
           └─────────────────┘ └─────────────────┘       └───────────┬────────────┘
           │                          │                            │
           ▼                          ▼                            ▼
  ┌──────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
  │ Neon PostgreSQL  │ <───> │ Entity Graph    │ <───> │ ML Inference & Decision│
  │ Relational DB    │       │ (Redis + SQL)   │       │ (XGBoost + SHAP + IF)  │
  └──────────────────┘       └─────────────────┘       └────────────────────────┘
```

### End-to-End Data Flow

$$\text{Transaction Event} \longrightarrow \text{FastAPI Ingestion} \longrightarrow \text{Kafka Raw Topic} \longrightarrow \text{Flink Stream Processor} \longrightarrow \text{Redis Feature Store} \longrightarrow \text{ML Inference (XGBoost + IF)} \longrightarrow \text{Decision Engine} \longrightarrow \text{Neon PostgreSQL} \longrightarrow \text{WebSocket / SSE Broadcast} \longrightarrow \text{React Dashboard}$$

---

## 🚦 Decision Engine Outcomes

Every transaction evaluated by Detexa is routed to one of four authoritative decision states:

| Outcome | Risk Level | Description | Action Taken |
| :--- | :--- | :--- | :--- |
| **`ALLOW`** | **Low** | Legitimate transaction passing all behavioral, velocity, and ML checks. | Approved immediately. |
| **`CHALLENGE`** | **Medium** | Elevated anomaly or velocity score; suspicious IP or unseen device. | Step-up authentication (OTP / 2FA / biometric). |
| **`REVIEW`** | **High** | High fraud probability, network risk indicators, or pattern anomalies. | Queued into Fraud Analyst triage console. |
| **`BLOCK`** | **Critical** | Velocity burst ($\ge 5\text{ tx/min}$), TOR/VPN high-risk node, graph link fraud ring, or critical ML score ($\ge 0.85$). | Automated instant decline & alert generation. |

---

## 📂 Project Structure

```
detexa/
├── backend/
│   ├── alembic/                      # Database migrations & versions
│   │   ├── versions/
│   │   │   └── 0001_initial_neon_schema.py
│   │   └── env.py
│   ├── app/
│   │   ├── api/                      # REST API endpoints & route handlers
│   │   │   └── v1/endpoints/         # auth, predict, streaming, alerts, transactions
│   │   ├── core/                     # Configuration, security (JWT/bcrypt), logging, Redis clients
│   │   ├── db/                       # SQLAlchemy models & database session setup
│   │   ├── decision/                 # Multi-rule Decision Engine & risk calculators
│   │   ├── feature_store/            # Redis feature store & sliding-window velocity aggregators
│   │   ├── features/                 # Dynamic canonical feature builder
│   │   ├── graph/                    # High-performance Redis + SQL graph link repository
│   │   ├── ml/                       # XGBoost credit fraud & Isolation Forest behavior models + SHAP
│   │   │   ├── models/               # Model inference classes
│   │   │   ├── pipelines/            # Feature engineering pipelines
│   │   │   └── saved/                # Production model artifacts (.pkl)
│   │   ├── models/                   # Core domain & metadata models
│   │   ├── schemas/                  # Pydantic v2 request/response schemas
│   │   ├── services/                 # Orchestration (fraud, behavior, alert, auth, streaming)
│   │   └── streaming/                # Kafka event producer, consumer & schemas
│   ├── data/                         # Evaluation benchmarks (dataset ignored by Git)
│   ├── flink/                        # Apache Flink stream worker & sliding-window job definitions
│   │   ├── config.py
│   │   └── run_job.py
│   ├── scripts/                      # Data generation, seeding & offline model training scripts
│   ├── tests/                        # Backend test suite (unit, API, E2E)
│   ├── Dockerfile                    # Multi-stage production FastAPI Dockerfile
│   ├── Dockerfile.worker             # Multi-stage lightweight Flink stream worker Dockerfile
│   ├── entrypoint.sh                 # Container startup with configuration validation
│   ├── requirements.txt              # Core production runtime dependencies
│   ├── requirements-worker.txt       # Dedicated Flink worker stream processing dependencies
│   └── requirements-dev.txt          # Development, testing, and CI dependencies
├── frontend/
│   ├── src/
│   │   ├── components/               # Navbar, charts, modals, data tables
│   │   ├── pages/                    # Overview, Transactions, Alerts, Live Predict, Behavior, Graph
│   │   └── services/                 # API client, WebSocket & SSE consumers
│   ├── nginx.conf                    # Production Nginx SPA & reverse proxy configuration
│   ├── Dockerfile                    # Multi-stage Nginx production container
│   ├── package.json                  # React + Vite dependencies
│   ├── tailwind.config.js            # Tailwind CSS styling configuration
│   └── vite.config.ts                # Vite build configuration
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated GitHub Actions CI/CD Pipeline
├── docs/
│   ├── DOCKER_AND_CI.md              # Docker & CI architecture documentation
│   └── NEO4J_AUDIT.md                # Architecture audit & graph modernization record
├── docker-compose.yml                # Production Compose stack
├── .env.example                      # Environment configuration template
├── .gitignore                        # Git exclusion rules
└── README.md                         # Platform documentation
```

---

## ⚙️ Core Implemented Features

- **Sub-35ms Real-Time Inference:** Direct in-place XGBoost Booster evaluation with active feature caching for ultra-fast transaction scoring (`/api/v1/predict/realtime`).
- **Distributed Event Ingestion:** Asynchronous publication to Kafka topic `detexa.transactions.raw` with automatic deduplication and partitioning (`/api/v1/streaming/transactions`).
- **Stateful Flink Stream Processing:** Continuous windowed stream processing ($1\text{m}, 5\text{m}, 1\text{h}$) computing transaction velocity, amount deviation ratios, and merchant diversity.
- **Graph Link Analysis with Redis & Postgres:** Real-time entity graph queries evaluating shared device fingerprints, card networks, and fraud rings across users without graph database memory overhead.
- **Sub-Millisecond Redis Feature Store:** In-memory sorted-set sliding window trackers and key-value cache for user profiles and velocity features.
- **Explainable Machine Learning:**
  - **Credit Card Fraud Classifier:** Supervised XGBoost model with SHAP `TreeExplainer` computing real-time feature attribution.
  - **Behavioral Anomaly Detector:** Unsupervised Isolation Forest analyzing login hours, typing velocity, mouse jitter, failed logins, and VPN/TOR network signatures.
- **Multi-Table Relational Persistence:** 11 normalized PostgreSQL tables managed through Alembic migrations (`users`, `transactions`, `devices`, `ip_addresses`, `merchants`, `fraud_alerts`, `fraud_predictions`, `behavior_logs`, `audit_logs`, `model_metadata`).
- **Live React + TypeScript Dashboard:** Nginx-served SPA displaying real-time metrics, interactive transaction inspector, alert triage management, live prediction playground, and WebSocket activity stream.

---

## 🔧 Environment Configuration

Copy the example environment configuration to create your local `.env`:

```bash
cp .env.example .env
cp .env.example backend/.env
```

### Key Environment Variables

| Variable | Default / Example Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Application environment (`development` / `production`). |
| `DATABASE_URL` | `postgresql://user:pass@ep-xxx.neon.tech/detexa?sslmode=require` | PostgreSQL / Neon connection string. |
| `REDIS_URL` | `redis://redis:6379/0` (or `redis://localhost:6379/0`) | Redis feature store URL. |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` (or `localhost:29092`) | Kafka broker address. |
| `FLINK_JOBMANAGER_HOST`| `flink-jobmanager` (or `localhost`) | Apache Flink JobManager host. |
| `FLINK_JOBMANAGER_PORT`| `8081` | Apache Flink REST API port. |
| `SECRET_KEY` | `detexa-super-secret-key-...` | Secret key used for JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT token expiration duration. |
| `FRAUD_THRESHOLD` | `0.60` | Score threshold for `REVIEW` / `CHALLENGE`. |
| `HIGH_RISK_THRESHOLD`| `0.85` | Score threshold for automated `BLOCK`. |

---

## 🚀 Quick Start with Docker (Recommended)

Start the entire distributed stack with a single command:

```bash
docker compose up --build -d
```

### Running Services

| Service | Container Name | URL / Port | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend Dashboard** | `detexa_frontend` | [http://localhost:5173](http://localhost:5173) | Production Nginx React SPA |
| **FastAPI Backend** | `detexa_backend` | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger OpenAPI |
| **Flink JobManager** | `detexa_flink_jobmanager`| [http://localhost:8081](http://localhost:8081) | Flink cluster & streaming metrics |
| **Flink TaskManager** | `detexa_flink_taskmanager`| Internal (4 slots) | Flink distributed compute slots |
| **Flink Stream Worker**| `detexa_flink_worker` | Internal | Kafka stream consumer & window processor |
| **Apache Kafka** | `detexa_kafka` | `localhost:9092` / `localhost:29092`| Distributed event broker (KRaft mode) |
| **Redis** | `detexa_redis` | `localhost:6379` | Feature store & sliding-window cache |
| **DB Migration** | `detexa_db_migrate` | One-shot | Automated safe Alembic migration runner |
| **Local PostgreSQL** *(Optional)* | `detexa_postgres_local` | `localhost:5432` | Optional offline DB (`--profile local-db`) |

Check status of all running containers:
```bash
docker compose ps
```

---

## 🤖 Continuous Integration & Testing

The repository includes a comprehensive GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`):
- **Backend Checks:** Python 3.11 syntax, import verification, and full pytest suite.
- **Frontend Checks:** Node.js 20 `npm ci`, TypeScript type checking, and production build verification.
- **Docker Validation:** Docker Compose validation and multi-stage image builds with GitHub Actions caching.
- **Integration Checks:** Real PostgreSQL and Redis container service tests executing database migrations and prediction workflows.

Run unit tests locally:
```bash
pytest backend/tests -v
```

---

## 🔌 API Reference Overview

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Authenticate user and receive JWT Bearer token | No |
| `POST` | `/api/v1/auth/register` | Register new user account | No |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Yes |
| `POST` | `/api/v1/predict/credit` | Full credit card fraud evaluation with SHAP explainability | Yes |
| `POST` | `/api/v1/predict/behavior`| Behavioral session anomaly scoring (Isolation Forest) | Yes |
| `POST` | `/api/v1/predict/realtime`| Ultra-low-latency real-time fraud scoring (<35ms) | Yes |
| `POST` | `/api/v1/streaming/transactions` | Asynchronous transaction ingestion into Kafka raw topic | Yes |
| `POST` | `/api/v1/streaming/transactions/process-sync` | End-to-end sync execution through Flink & ML pipeline | Yes |
| `GET` | `/api/v1/alerts` | List and filter fraud alerts | Yes |
| `PUT` | `/api/v1/alerts/{id}/status` | Update alert triage status (`OPEN`, `REVIEWED`, `RESOLVED`) | Yes |
| `GET` | `/api/v1/alerts/stats` | Retrieve aggregate fraud KPIs & risk metrics | Yes |
| `GET` | `/api/v1/transactions` | Query recent persisted transactions | Yes |
| `WS` | `/api/v1/streaming/ws/dashboard` | WebSocket stream for live real-time dashboard events | No |
| `GET` | `/api/v1/streaming/events/stream` | Server-Sent Events (SSE) stream for transactions | No |
| `GET` | `/health` | Healthcheck endpoint reporting system status | No |

---

## 📄 License

MIT License. Designed and engineered for high-throughput, low-latency financial fraud detection.
