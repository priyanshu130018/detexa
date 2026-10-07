# 🛡️ Detexa – Real-Time Banking Fraud Detection Platform

Detexa is an enterprise-grade, real-time banking fraud detection and risk scoring platform. It combines distributed event streaming, stateful stream processing, graph-based relationship intelligence, in-memory feature stores, and explainable machine learning models to intercept fraudulent financial transactions with sub-35ms latency.

---

## 🏛️ System Architecture

```
                                  DETEXA PLATFORM ARCHITECTURE

  ┌──────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
  │   React + Vite   │ <───> │ FastAPI Backend │ ────> │  Apache Kafka Broker   │
  │ Frontend (TSX)   │ (SSE) │  REST & WS Hub  │       │ (detexa.transactions)  │
  └──────────────────┘       └─────────────────┘       └───────────┬────────────┘
           ▲                          │                            │
           │                          ▼                            ▼
           │                 ┌─────────────────┐       ┌────────────────────────┐
           │ (REST / Auth)   │  Redis Feature  │       │ Apache Flink Processor │
           │                 │   Store & TTL   │ <───> │   (Windowed Velocity)  │
           │                 └─────────────────┘       └───────────┬────────────┘
           │                          ▲                            │
           ▼                          ▼                            ▼
  ┌──────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
  │ Neon PostgreSQL  │ <───> │  Neo4j Graph DB │ <───> │ ML Inference & Decision│
  │ Relational DB    │       │ (Device / Link) │       │ (XGBoost + SHAP + IF)  │
  └──────────────────┘       └─────────────────┘       └────────────────────────┘
```

### End-to-End Data Flow

$$\text{Transaction Event} \longrightarrow \text{FastAPI Ingestion} \longrightarrow \text{Kafka Raw Topic} \longrightarrow \text{Flink Stream Processor} \longrightarrow \text{Redis / Neo4j Feature Store} \longrightarrow \text{ML Inference (XGBoost + IF)} \longrightarrow \text{Decision Engine} \longrightarrow \text{Neon PostgreSQL} \longrightarrow \text{WebSocket / SSE Broadcast} \longrightarrow \text{React Dashboard}$$

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
│   │   ├── core/                     # Configuration, security (JWT/bcrypt), logging, Redis/Neo4j clients
│   │   ├── db/                       # SQLAlchemy models & database session setup
│   │   ├── decision/                 # Multi-rule Decision Engine & risk calculators
│   │   ├── feature_store/            # Redis feature store & sliding-window velocity aggregators
│   │   ├── features/                 # Dynamic canonical feature builder
│   │   ├── graph/                    # Neo4j Cypher queries & link analysis repository
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
│   ├── tests/                        # Backend test suite
│   ├── Dockerfile                    # Multi-stage production Dockerfile
│   ├── entrypoint.sh                 # Container startup with automated Alembic migration
│   ├── requirements.txt              # Python runtime dependencies
│   └── test_integration_all.py       # Full Docker integration & resiliency test suite
├── frontend/
│   ├── src/
│   │   ├── components/               # Navbar, charts, modals, data tables
│   │   ├── pages/                    # Overview, Transactions, Alerts, Live Predict, Behavior, Graph
│   │   └── services/                 # API client, WebSocket & SSE consumers
│   ├── package.json                  # React + Vite dependencies
│   ├── tailwind.config.js            # Tailwind CSS styling configuration
│   └── vite.config.ts                # Vite build configuration
├── docker-compose.yml                # Multi-container orchestration (Backend, Frontend, Kafka, Flink, Redis, Neo4j)
├── .env.example                      # Environment configuration template
├── .gitignore                        # Git exclusion rules (CSVs, logs, credentials ignored)
├── requirements.txt                  # Root-synchronized Python dependencies
└── README.md                         # Platform documentation
```

---

## ⚙️ Core Implemented Features

- **Sub-35ms Real-Time Inference:** Direct in-place XGBoost C++ Booster evaluation with active caching for high-throughput transaction authorization (`/api/v1/predict/realtime`).
- **Distributed Event Ingestion:** Asynchronous publication to Kafka topic `detexa.transactions.raw` with automatic deduplication and partitioning (`/api/v1/streaming/transactions`).
- **Stateful Flink Stream Processing:** Continuous tumbling and sliding window calculations ($1\text{m}, 5\text{m}, 1\text{h}$) computing transaction velocity, amount deviation ratios, and merchant diversity.
- **Graph Link Analysis with Neo4j:** Real-time Cypher entity graph queries evaluating shared device fingerprints, card networks, and fraud rings across users.
- **Sub-Millisecond Redis Feature Store:** In-memory sorted-set sliding window trackers and key-value cache for user profiles and velocity features.
- **Explainable Machine Learning:**
  - **Credit Card Fraud Classifier:** Supervised XGBoost model with SHAP `TreeExplainer` computing real-time feature attribution.
  - **Behavioral Anomaly Detector:** Unsupervised Isolation Forest analyzing login hours, typing velocity, mouse jitter, failed logins, and VPN/TOR network signatures.
- **Multi-Table Relational Persistence:** 11 normalized PostgreSQL tables managed through Alembic migrations (`users`, `transactions`, `devices`, `ip_addresses`, `merchants`, `fraud_alerts`, `fraud_predictions`, `behavior_logs`, `audit_logs`, `model_metadata`).
- **Live React + TypeScript Dashboard:** Dark-mode analytics UI displaying real-time metrics, interactive transaction inspector, alert triage management, live prediction playground, and WebSocket activity stream.

---

## 📊 Dataset & Kaggle Download Instructions

> [!IMPORTANT]
> The banking transaction dataset is **NOT** included in the Git repository and must be downloaded separately.

### Expected Dataset Details
- **Dataset Name:** `indian_banking_transactions.csv`
- **Expected Directory:** `data/raw/` (or `backend/data/`)
- **Target File Path:** `data/raw/indian_banking_transactions.csv`

### Step-by-Step Setup:
1. Download `indian_banking_transactions.csv` from Kaggle.
2. Create the raw data directory in your project root:
   ```bash
   mkdir -p data/raw
   ```
3. Place the downloaded CSV file into `data/raw/`:
   ```bash
   cp /path/to/downloaded/indian_banking_transactions.csv data/raw/indian_banking_transactions.csv
   ```
4. Run the training or preprocessing pipeline if retraining models:
   ```bash
   python backend/scripts/train_models.py
   ```

*(If the CSV is not supplied, built-in synthetic data generators enable immediate functional testing without manual downloads).*

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
| `NEO4J_URI` | `bolt://neo4j:7687` (or `bolt://localhost:7687`) | Neo4j Bolt protocol URI. |
| `NEO4J_USER` | `neo4j` | Neo4j database user. |
| `NEO4J_PASSWORD` | `detexa_neo4j_password` | Neo4j database password. |
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
| **Frontend Dashboard** | `detexa_frontend` | [http://localhost:5173](http://localhost:5173) | React + TypeScript UI |
| **FastAPI Backend** | `detexa_backend` | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger OpenAPI |
| **Flink JobManager** | `detexa_flink_jobmanager`| [http://localhost:8081](http://localhost:8081) | Flink cluster & streaming metrics |
| **Flink TaskManager** | `detexa_flink_taskmanager`| Internal (4 slots) | Flink distributed compute slots |
| **Flink Stream Worker**| `detexa_flink_worker` | Internal | Kafka stream consumer & window processor |
| **Apache Kafka** | `detexa_kafka` | `localhost:9092` / `localhost:29092`| Distributed event broker |
| **Redis** | `detexa_redis` | `localhost:6379` | Feature store & sliding-window cache |
| **Neo4j Browser** | `detexa_neo4j` | [http://localhost:7474](http://localhost:7474) | Graph database visualizer |

Check status of all running containers:
```bash
docker compose ps
```

---

## 💻 Running Locally (Without Docker)

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate       # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup

```bash
# In a second terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Running Integration Tests

Detexa includes a full end-to-end integration test suite that verifies PostgreSQL persistence, Redis features, Neo4j Cypher queries, Kafka publish/consume, ML inference, and streaming sync pipelines.

### Run Tests Inside Docker Container:

```bash
docker exec detexa_backend python test_integration_all.py
```

### Run Unit Tests with Pytest:

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
