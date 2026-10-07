# Detexa - Real-Time Banking Fraud Detection Platform

Detexa is an enterprise-grade, real-time banking fraud prevention and risk scoring platform. It combines sub-millisecond machine learning inference, real-time stream processing, distributed in-memory state, and graph entity resolution to intercept fraudulent transactions, behavioral anomalies, and organized fraud syndicates before financial settlement.

---

## 📌 Problem Detexa Solves

Modern banking platforms process millions of concurrent financial transactions. Traditional rule engines and batch-oriented fraud detection systems suffer from severe limitations:
1. **High Latency:** Batch detection catches fraud hours or days after funds have left the institution.
2. **High False Positive Rates:** Static rules decline legitimate customer transactions, creating user friction and lost revenue.
3. **Syndicate Blindness:** Single-point evaluation misses coordinated fraud rings sharing devices, proxy subnets, and stolen identities across multiple accounts.
4. **Lack of Explainability:** Black-box ML models fail compliance and AI governance requirements without actionable explanations.

Detexa solves this by deploying a **hybrid detection architecture**:
- **Sub-millisecond ML Scoring:** In-memory XGBoost and Isolation Forest inference ($< 1\text{ ms}$).
- **Sliding-Window Feature Store:** In-memory Redis state tracking velocity and rolling totals across 1m, 5m, 15m, 1h, and 24h intervals.
- **Graph Entity Resolution:** Neo4j multi-hop entity graphs identifying shared devices, proxy collusion, and fraud rings.
- **Deterministic Business Rules:** Dynamic policy engine arbitrating between `ALLOW`, `CHALLENGE` (MFA), `REVIEW` (Analyst Triage), and `BLOCK`.
- **SHAP Explainability:** Real-time TreeSHAP feature contribution breakdowns for every transaction score.

---

## 🚀 Key Features

- **360° Real-Time Transaction Scoring:** Evaluates financial details, device fingerprints, geo-IP telemetry, behavioral biometrics, Redis sliding windows, and Neo4j graph signals.
- **Explainable AI (XAI):** Directional SHAP feature importance charts detailing why a transaction was flagged.
- **Graph Syndicate Detection:** Interactive multi-hop entity relationship graph resolving shared hardware, IP subnets, and fraud rings.
- **Behavioral Anomaly Detection:** Isolation Forest model monitoring user session dynamics, typing cadence, mouse velocity, and Tor/VPN usage.
- **Dynamic Decision Arbitration:** Configurable threshold bands and rule overrides with audit justification logs.
- **Real-Time Live Dashboard:** Instant updates via WebSockets and Server-Sent Events (SSE) with live throughput and incident triage feeds.
- **Strict 4-Color UI (Dark & Light Mode):** High-contrast, accessibility-focused interface strictly using White, Black, Blue, and Red palettes.

---

## 🏛️ High-Level Architecture & Data Flow

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Client / Core  │ ────> │  FastAPI Server │ ────> │  Apache Kafka   │
│  Banking System │       │  (Port 8000)    │       │ (transactions.raw)
└─────────────────┘       └─────────────────┘       └────────┬────────┘
                                   │                         │
                                   ▼                         ▼
                          ┌─────────────────┐       ┌─────────────────┐
                          │ PostgreSQL/Neon │       │  Apache Flink   │
                          │ (Persistent DB) │       │  (Stream Job)   │
                          └────────┬────────┘       └────────┬────────┘
                                   ▲                         │
                                   │                         ▼
                          ┌────────┴────────┐       ┌─────────────────┐
                          │ Decision Engine │ <──── │   Redis + Neo4j │
                          │ & ML Inference  │       │ (Feature Store) │
                          └────────┬────────┘       └─────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Real-time Stream│ ────> React Dashboard (Port 5173)
                          │ (WebSocket/SSE) │
                          └─────────────────┘
```

### End-to-End Transaction Lifecycle:
1. **Ingestion:** Transaction arrives via `POST /api/v1/transactions` or Kafka topic `transactions.raw`.
2. **State Enrichment:** Real-time sliding window aggregates are read/updated in **Redis**; multi-hop entity connections are queried from **Neo4j**.
3. **ML Inference:** Feature vector (61 canonical features) is passed to **XGBoost** for probability estimation and **TreeSHAP** computation.
4. **Decision Engine:** Evaluates business policy rules against ML scores and outputs verdict (`ALLOW`, `CHALLENGE`, `REVIEW`, `BLOCK`).
5. **Persistence & Incident Alerting:** Results are recorded to **PostgreSQL/Neon**; high-risk anomalies trigger security alerts on `fraud.alerts`.
6. **Live Broadcast:** Updates broadcast via WebSockets / SSE to the **React dashboard** in sub-second latency.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Tailwind CSS, Vite, Recharts, Lucide Icons |
| **Backend API** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Uvicorn |
| **Machine Learning** | XGBoost, Scikit-learn (Isolation Forest), SHAP, Joblib, NumPy, Pandas |
| **Stream Processing** | Apache Kafka, Apache Flink (JobManager & TaskManager) |
| **In-Memory Store** | Redis (Sliding window aggregations, velocity keys with TTL) |
| **Graph Database** | Neo4j Community (Cypher queries, multi-hop entity resolution) |
| **Relational Database** | PostgreSQL / Neon Cloud, Alembic migrations |
| **Containerization** | Docker, Docker Compose |

---

## 📂 Project Structure

```text
Detexa/
├── backend/                  # FastAPI Application & ML Engine
│   ├── alembic/              # Database migration scripts
│   ├── app/
│   │   ├── api/v1/           # Modular REST & WebSocket endpoints
│   │   ├── core/             # Configuration, security, logging, Redis pool
│   │   ├── db/               # SQLAlchemy engine, session, base models
│   │   ├── ml/               # XGBoost, Isolation Forest, feature pipelines
│   │   ├── models/           # SQLAlchemy DB models & Pydantic schemas
│   │   ├── services/         # Business logic, graph, feature store, alerts
│   │   └── streaming/        # Kafka producers/consumers, Flink jobs
│   ├── models/               # Serialized ML model artifacts (.joblib)
│   ├── Dockerfile            # Production backend Docker configuration
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React 18 + TypeScript Application
│   ├── src/
│   │   ├── components/       # UI components (badges, gauges, charts, layouts)
│   │   ├── context/          # ThemeContext (4-color dark/light), RealtimeContext
│   │   ├── pages/            # Dashboard, Transactions, Alerts, Graph, Sandbox
│   │   ├── services/         # Axios API clients
│   │   └── types/            # TypeScript interfaces & domain types
│   ├── Dockerfile            # Production frontend Docker configuration
│   └── package.json          # Node dependencies
├── data/                     # Dataset directory (.gitignored)
│   └── raw/                  # Place raw CSV datasets here (e.g. Kaggle data)
├── docs/                     # Living Documentation Suite
│   ├── README.md             # Project overview & quickstart (this file)
│   ├── ARCHITECTURE.md       # Deep architectural specifications & data flows
│   ├── DEVELOPMENT.md        # Local development, environment, training guide
│   ├── API.md                # Complete REST, WebSocket, & SSE endpoint docs
│   └── SECURITY.md           # Implemented security controls & hardening guide
├── docker-compose.yml        # Multi-container orchestration
└── .env                      # Unified environment variable configuration
```

---

## 🐳 Docker Services Topology

The complete platform runs in isolated Docker containers defined in `docker-compose.yml`:

| Container | Service | Internal Port | Host Port | Purpose |
|---|---|---|---|---|
| `detexa-frontend` | React UI | 5173 | `5173` | Web dashboard & investigation UI |
| `detexa-backend` | FastAPI API | 8000 | `8000` | Core API, ML inference, and DB engine |
| `detexa-kafka` | Apache Kafka | 9092 | `9094` | High-throughput streaming message broker |
| `detexa-zookeeper` | Zookeeper | 2181 | `2181` | Kafka cluster coordination |
| `detexa-flink-jobmanager`| Flink Master | 8081 | `8081` | Stream job coordinator & Web UI |
| `detexa-flink-taskmanager`| Flink Worker | - | - | Distributed streaming task worker |
| `detexa-redis` | Redis Cache | 6379 | `6379` | Sub-millisecond sliding window state |
| `detexa-neo4j` | Neo4j Graph | 7474, 7687 | `7474`, `7687` | Entity graph database & browser |

---

## ⚡ Quick Start with Docker

### 1. Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- 8 GB+ RAM recommended

### 2. Setup Environment
Ensure `.env` exists in the project root:
```bash
cp .env.example .env  # or verify existing .env
```

### 3. Start the Complete Stack
```bash
docker compose up --build -d
```

### 4. Verify Services
Check container health:
```bash
docker compose ps
```

Access Web Interfaces:
- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **FastAPI Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Flink Web Dashboard:** [http://localhost:8081](http://localhost:8081)
- **Neo4j Browser:** [http://localhost:7474](http://localhost:7474)

---

## 📊 Dataset & Kaggle Setup

Detexa uses credit card and transaction anomaly datasets (such as `indian_banking_transactions.csv`). 

> **Important:** The dataset files are excluded from version control via `.gitignore`.

To use the dataset for local model training or bulk ingestion:
1. Download the banking transaction dataset from Kaggle.
2. Create directory `data/raw/` if it does not exist:
   ```bash
   mkdir -p data/raw
   ```
3. Place the CSV file at:
   ```text
   data/raw/indian_banking_transactions.csv
   ```
4. Run the training or ingestion scripts detailed in [`docs/DEVELOPMENT.md`](DEVELOPMENT.md).

---

## 📚 Complete Documentation Suite

For comprehensive guides and technical deep-dives, refer to:
- 🏛️ **[ARCHITECTURE.md](ARCHITECTURE.md):** Deep dive into Flink, Kafka, Redis, Neo4j, ML pipelines, and data flow topologies.
- 💻 **[DEVELOPMENT.md](DEVELOPMENT.md):** Local setup, model training/retraining, database migrations, and debugging workflows.
- 🔌 **[API.md](API.md):** Complete REST API endpoints, schemas, WebSocket channels, and SSE specifications.
- 🛡️ **[SECURITY.md](SECURITY.md):** Authentication, JWT handling, access control, and operational security guidelines.
