# DETEXA: Enterprise AI Real-Time Fraud Detection & Prevention Platform
## Final Implementation & System Architecture Report

---

### Executive Summary

**Detexa** is an enterprise-grade, low-latency, real-time AI-powered financial fraud detection and prevention platform. It combines distributed event streaming (Apache Kafka), stateful stream processing (Apache Flink), sub-millisecond hot-feature caching (Redis), graph-based collusion analysis (Neo4j), multi-model machine learning inference (XGBoost/LightGBM/ONNX), and a deterministic 4-tier decision arbitration engine (ALLOW, REVIEW, CHALLENGE, BLOCK). The system persists immutable audit trails and transactions in Neon Cloud PostgreSQL and streams live intelligence to a modern React 18 + TypeScript + Tailwind CSS operations dashboard via WebSockets and Server-Sent Events (SSE).

---

## 1. What Was Built

The Detexa platform consists of the following core functional subsystems:

1. **Distributed Event Streaming Ingestion**: Real-time event publisher and consumer using Apache Kafka (KRaft mode) capable of processing thousands of payment events per second.
2. **Stateful Stream Processing Pipeline**: Apache Flink streaming engine performing continuous tumbling and sliding-window aggregations (1-minute, 5-minute, 1-hour windows) for velocity, amount deviations, device hops, and failed authentication counters.
3. **Real-Time Feature Store**: High-throughput Redis 7 feature store managing sliding counters, historical transaction sets, hardware fingerprints, and user behavior caches with automatic TTL management and in-memory fallback.
4. **Graph Intelligence & Syndicate Detection**: Neo4j graph database modeling multi-entity relationships (`User` $\to$ `Device` $\to$ `IP` $\to$ `Merchant` $\to$ `Transaction`) with Cypher graph queries to detect shared hardware, IP proxy networks, and fraud rings.
5. **Unified Feature Engineering Layer (`UnifiedFeatureEngine`)**: Schema-versioned (`FEATURE_SCHEMA_V2`) 40+ dimensional feature extractor that guarantees complete feature parity across offline model training, batch evaluation, and online sub-millisecond inference.
6. **Multi-Model Machine Learning Engine**: Pre-trained ensemble classifiers (XGBoost, LightGBM, Random Forest, Isolation Forest) exported to ONNX runtime with pre-computed scalers and safe fallback score evaluation.
7. **Configurable 4-Tier Decision Engine**: Rule-based and score-based policy arbiter enforcing configurable business rules (velocity bursts, amount ceilings, graph risk thresholds, nocturnal timing) and outputting `ALLOW`, `CHALLENGE`, `REVIEW`, or `BLOCK` with human-in-the-loop analyst override logging.
8. **Cloud Relational Persistence**: Cloud Neon PostgreSQL with SSL support, SQLAlchemy 2.0 ORM, connection pooling (`QueuePool`), transaction rollback safety, and full indexing.
9. **Real-Time Bidirectional Event Bus**: FastAPI WebSocket and Server-Sent Events (SSE) hub (`RealtimeBroadcaster`) dispatching live transaction streams, fraud alerts, and decision updates to connected clients with a 15-second heartbeat watchdog.
10. **Modern Operations Dashboard**: React 18 + TypeScript + Tailwind CSS single-page application featuring interactive risk distribution charts, transaction filters, alert triage modals, graph relationship visualizers, and live telemetry indicators.
11. **Containerized Deployment Architecture**: Multi-container Docker Compose setup orchestrating 7 microservices with isolated internal networking and volume management.

---

## 2. Final Architecture

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Ingestion Layer"]
        CLI["Payment Gateway / Simulation Client"]
        FE["React + TS Dashboard (Vite :5173)"]
    end

    subgraph MessagingLayer ["Distributed Event Streaming"]
        KAFKA["Apache Kafka (KRaft :9092)"]
        TOPIC_RAW["Topic: detexa.transactions.raw"]
        TOPIC_ALERT["Topic: detexa.alerts.high_risk"]
    end

    subgraph StreamLayer ["Stream Processing Layer"]
        FLINK_JM["Flink JobManager (:8081)"]
        FLINK_TM["Flink TaskManager"]
    end

    subgraph StorageLayer ["Feature & Graph Intelligence"]
        REDIS[("Redis 7 Feature Store (:6379)")]
        NEO4J[("Neo4j Graph Database (:7687 / :7474)")]
        NEON[("Neon Cloud PostgreSQL (SSL)")]
    end

    subgraph BackendLayer ["FastAPI Core Backend (:8000)"]
        API["FastAPI REST & Auth Gateway"]
        UFE["Unified Feature Engine (v2)"]
        ML["ML Inference Engine (XGBoost / ONNX)"]
        DE["Fraud Decision Engine (4 Tiers)"]
        RTB["RealtimeBroadcaster (WS / SSE)"]
    end

    CLI -->|POST /api/v1/transactions| API
    CLI -->|Produce Raw Events| KAFKA
    KAFKA --> TOPIC_RAW
    TOPIC_RAW --> FLINK_JM
    FLINK_JM --> FLINK_TM
    FLINK_TM -->|Update Hot Counters| REDIS

    API --> UFE
    UFE -->|Query Sliding Windows| REDIS
    UFE -->|Query Identity Graph| NEO4J
    UFE -->|Build Feature Vector| ML
    ML -->|Fraud Score| DE
    DE -->|ALLOW / REVIEW / CHALLENGE / BLOCK| API

    API -->|Persist Txn, Decision, Alert| NEON
    API -->|Publish High Risk Alerts| KAFKA
    KAFKA --> TOPIC_ALERT
    API -->|Broadcast Event| RTB
    RTB -->|WebSocket / SSE Stream| FE
    FE -->|REST API Requests| API
```

---

## 3. Backend Components

The backend is built with **FastAPI**, **SQLAlchemy 2.0**, and **Pydantic v2**, structured as follows:

```
backend/app/
├── api/
│   ├── deps.py                      # Reusable FastAPI dependency injections (DB, Auth, Repos, Services)
│   └── v1/
│       ├── api.py                   # Central API Router aggregating all endpoint modules
│       └── endpoints/
│           ├── auth.py              # User authentication, JWT issuance, password hashing
│           ├── transactions.py      # Transaction querying, filtering, pagination, and detail inspection
│           ├── decisions.py         # AI decisions listing, manual override audit, rule policy introspection
│           ├── alerts.py            # Alert triage, status updates (OPEN, INVESTIGATING, RESOLVED, DISMISSED)
│           ├── dashboard.py         # KPI statistics, time-series trends, risk tier breakdown, geo distributions
│           ├── feature_store.py     # Redis hot-feature inspection and manual cache invalidation
│           ├── graph.py             # Neo4j graph cluster analysis and entity risk lookups
│           ├── behavior.py          # User behavioral telemetry logging (typing speed, anomaly scores)
│           ├── realtime.py          # WebSocket (`/ws/events`), SSE (`/events/stream`), and test event publisher
│           └── health.py            # Deep multi-dependency healthcheck (PostgreSQL, Redis, Neo4j, Kafka)
├── core/
│   ├── config.py                    # Pydantic BaseSettings loading all environment configurations
│   ├── exceptions.py                # Domain exception hierarchy (DetexaBaseException, EntityNotFoundException, etc.)
│   ├── security.py                  # Password hashing (bcrypt) and JWT encode/decode utilities
│   ├── redis.py                     # Redis client lifecycle, connection pooling, auto-reconnection
│   ├── kafka.py                     # Kafka producer/consumer lifecycle management
│   └── realtime_broadcaster.py      # Thread-safe WebSocket & SSE broadcast engine with stale connection watchdog
├── db/
│   ├── session.py                   # SQLAlchemy engine configuration with connection pooling and session lifecycle
│   └── models.py                    # Declarative ORM models (User, Transaction, DecisionLog, Alert, etc.)
├── feature_store/
│   ├── hot_features.py              # Pydantic data schemas for Redis hot features
│   ├── redis_store.py               # Low-level Redis feature store service with in-memory fallback
│   └── service.py                   # High-level feature store orchestrator
├── graph/
│   ├── client.py                    # Neo4j bolt driver lifecycle management
│   ├── repository.py                # Cypher query execution for nodes and relationships
│   └── service.py                   # Graph feature extraction (shared devices, shared IPs, cluster risk)
├── ml/
│   ├── schema.py                    # Canonical feature schema definitions (FEATURE_SCHEMA_V2)
│   ├── engine.py                    # UnifiedFeatureEngine combining transaction, Redis, and Neo4j features
│   ├── models.py                    # Model wrapper classes (CreditFraudModel, BehaviorAnomalyModel)
│   ├── inference.py                 # FraudInferenceService executing model scoring and ONNX inference
│   └── saved/                       # Serialized model artifacts (.joblib, .json, .onnx)
├── repositories/
│   ├── transaction_repo.py          # Data access layer for transactions with dynamic SQL filters
│   ├── decision_repo.py             # Data access layer for decision records and override logs
│   ├── alert_repo.py                # Data access layer for fraud alerts
│   ├── user_repo.py                 # Data access layer for user authentication and authorization
│   └── behavior_repo.py             # Data access layer for user behavioral telemetry
└── services/
    ├── transaction_service.py       # Transaction orchestration, scoring pipeline trigger, alert generation
    ├── decision_service.py          # Decision engine execution and analyst override logic
    ├── alert_service.py             # Alert lifecycle management and status transitions
    ├── auth_service.py              # User authentication, JWT generation, user registration
    └── dashboard_service.py         # Dashboard KPI aggregation with Redis caching
```

---

## 4. Frontend Components

The frontend is built with **React 18**, **TypeScript**, **Tailwind CSS**, and **Lucide Icons**, organized into a modular design system:

```
frontend/src/
├── components/
│   ├── common/
│   │   ├── Navbar.tsx               # Top navigation bar with real-time connection status indicator
│   │   ├── Sidebar.tsx              # Collapsible navigation drawer for dashboard routing
│   │   ├── StatCard.tsx             # Reusable KPI card with trend indicators and colored palettes
│   │   ├── RiskBadge.tsx            # Visual risk tier indicator (Low, Medium, High, Critical)
│   │   └── DecisionBadge.tsx        # Decision chip (ALLOW, REVIEW, CHALLENGE, BLOCK)
│   ├── dashboard/
│   │   ├── TransactionTable.tsx     # Sortable, paginated transaction data grid
│   │   ├── AlertCard.tsx            # Card component for triaging high-risk fraud alerts
│   │   ├── GraphNetworkView.tsx     # Visual relationship renderer for user-device-IP graphs
│   │   └── FeatureImportanceChart.tsx# Visual breakdown of top contributing fraud features
│   └── layout/
│       └── Layout.tsx               # Master app wrapper containing responsive Navbar and Sidebar
├── context/
│   ├── AuthContext.tsx              # React Context for JWT auth state, login, logout, and token refresh
│   └── RealtimeContext.tsx          # Real-time event subscription context managing WebSocket & SSE connections
├── pages/
│   ├── LoginPage.tsx                # Secure analyst login screen
│   ├── OverviewPage.tsx             # Executive command center with live KPIs, charts, and transaction feed
│   ├── TransactionsPage.tsx         # Comprehensive transaction explorer with advanced search and filters
│   ├── TransactionDetailPage.tsx   # Detailed view of a single transaction (PCA features, device, IP, merchant)
│   ├── AlertsPage.tsx               # Fraud alert management workbench with status transitions and notes
│   ├── FraudInvestigationPage.tsx   # Live scenario simulator to test feature extraction and decision rules
│   ├── GraphInvestigationPage.tsx   # Graph-based fraud syndicate explorer with Cypher relationship visualizer
│   └── ModelStatsPage.tsx           # ML model governance page displaying ROC-AUC, PR-AUC, and feature rankings
├── services/
│   ├── api.service.ts               # Axios client with request/response interceptors for JWT injection
│   ├── realtime.service.ts          # Resilient WebSocket state machine with auto-reconnect and SSE fallback
│   ├── auth.service.ts              # Authentication API service
│   ├── transaction.service.ts       # Transaction API service
│   ├── alert.service.ts             # Alert management API service
│   ├── decision.service.ts          # Decision and override API service
│   └── graph.service.ts             # Graph query API service
└── types/
    └── index.ts                     # TypeScript interfaces matching backend Pydantic schemas
```

---

## 5. Kafka Flow

Detexa uses **Apache Kafka 3.7** running in **KRaft mode** (no ZooKeeper dependency):

```mermaid
sequenceDiagram
    participant App as FastAPI / Ingestion Client
    participant K_Raw as Kafka Topic: detexa.transactions.raw
    participant Flink as Apache Flink Streaming Engine
    participant K_Alert as Kafka Topic: detexa.alerts.high_risk
    participant Sink as Alert Notification Consumer

    App->>K_Raw: Produce Transaction Event (JSON)
    K_Raw->>Flink: Consume Stream in Real Time
    Flink->>Flink: Compute Sliding Window Features
    App->>K_Alert: Produce High-Risk Alert Event (if Score > 0.85)
    K_Alert->>Sink: Consume and Notify SecOps / Webhook
```

- **Topic Configurations**:
  - `detexa.transactions.raw`: Partitioned raw transaction event ingestion stream.
  - `detexa.alerts.high_risk`: High-priority alert stream dispatched when risk evaluation triggers `BLOCK` or `REVIEW`.
- **Fault-Tolerant Features**:
  - Asynchronous background dispatch with bounded local queue fallback.
  - Safe circuit-breaker preventing API blocking during Kafka broker downtime.

---

## 6. Flink Flow

The **Apache Flink 1.18** stream processing layer operates independently of the FastAPI web application:

```mermaid
flowchart LR
    K_IN[Kafka Raw Stream] --> DESER[JSON Deserializer & Watermark Assigner]
    DESER --> KEY[KeyedStream by user_id]
    KEY --> W1[1-Minute Sliding Window: Velocity]
    KEY --> W2[5-Minute Tumbling Window: Failed Auth Count]
    KEY --> W3[1-Hour Sliding Window: Amount Spikes]
    KEY --> STATE[Keyed ValueState: Last Device & IP]
    
    W1 --> SINK[Redis Hot Feature Store Sink]
    W2 --> SINK
    W3 --> SINK
    STATE --> SINK
```

- **Window Operations**:
  - **Transaction Velocity**: Number of transactions in the last 1 minute and 5 minutes.
  - **Amount Aggregations**: Rolling sum and rolling average transaction amount over 1 hour.
  - **Device / IP Shifts**: Identification of rapid device or IP changes within sliding windows.
  - **Failed Authentication Counters**: Rolling count of authorization failures in the last 5 minutes.
- **State Checkpointing**: RocksDB / Filesystem state checkpointing configured to `file:///tmp/flink-checkpoints`.

---

## 7. Redis Usage

Redis 7 serves as the sub-millisecond **Real-Time Feature Store** and **Application Cache**:

| Key Pattern | Data Structure | TTL | Purpose |
| :--- | :--- | :--- | :--- |
| `feat:user:{id}:velocity_1m` | String / Counter | 60s | Count of transactions in the last 60 seconds |
| `feat:user:{id}:velocity_5m` | String / Counter | 300s | Count of transactions in the last 5 minutes |
| `feat:user:{id}:amounts_1h` | List / Sorted Set | 3600s | Rolling transaction amounts for deviation analysis |
| `feat:user:{id}:failed_auth_5m` | String / Counter | 300s | Rolling count of failed authentication attempts |
| `feat:user:{id}:devices` | Set | 86400s (24h) | Distinct device fingerprints used in the last 24h |
| `feat:user:{id}:ips` | Set | 86400s (24h) | Distinct IP addresses used in the last 24h |
| `feat:user:{id}:last_txn` | Hash | 86400s (24h) | Timestamp, amount, merchant, and geo of last transaction |
| `cache:dashboard:kpis` | String / JSON | 30s | Pre-calculated dashboard summary KPI metrics |

- **Resiliency**: Built-in `RedisFeatureStoreService` includes automatic liveness checks and graceful in-memory fallback if Redis is unavailable.

---

## 8. Neo4j Usage

Neo4j Community Edition 5.18 acts as the **Graph Intelligence Engine**, modeling complex identity and transaction networks:

### Graph Schema
- **Nodes**:
  - `(:User {id, name, email, risk_tier})`
  - `(:Device {fingerprint, device_type, os, browser, is_emulator})`
  - `(:IP {address, country, is_vpn, is_tor, risk_score})`
  - `(:Merchant {id, name, category, risk_level})`
  - `(:Transaction {id, ref, amount, timestamp, is_fraud})`
- **Relationships**:
  - `(:User)-[:USES_DEVICE {first_seen, last_seen, count}]->(:Device)`
  - `(:User)-[:USES_IP {first_seen, last_seen, count}]->(:IP)`
  - `(:User)-[:TRANSACTED_WITH {total_amount, count}]->(:Merchant)`
  - `(:User)-[:INITIATED]->(:Transaction)`
  - `(:Transaction)-[:TRANSACTED_AT]->(:Merchant)`

### Key Graph Queries
1. **Shared Device Detection**: Finds all distinct users sharing the same hardware fingerprint.
2. **Shared IP Proxy Network**: Detects multiple accounts operating through identical VPN/Tor exit nodes.
3. **Syndicate Degree Centrality**: Measures the density of interconnected users and devices to calculate a `graph_risk_score` ($0.0 \le s \le 1.0$).

---

## 9. ML Pipeline

### Models & Performance
- **Primary Model**: `CreditFraudModel` (XGBoost Classifier + Scikit-Learn Pipeline).
- **Secondary Anomaly Model**: `BehaviorAnomalyModel` (Isolation Forest for behavioral telemetry).
- **Training Artifacts**: Pre-trained on credit card fraud datasets with extreme class imbalance mitigation (ScalePosWeight, SMOTE).
- **Inference Latency**: $\le 12\text{ms}$ on CPU; ONNX runtime export supported for high-throughput batch scoring.

### Feature Schema (`FEATURE_SCHEMA_V2`)
The unified feature vector consists of 40+ standardized features:
1. **Transaction Features**: `amount`, `log_amount`, `hour_of_day`, `day_of_week`, `is_weekend`, `is_night_time`, `pca_v1` ... `pca_v28`.
2. **Redis Real-Time Features**: `velocity_1m`, `velocity_5m`, `amount_deviation_score`, `failed_auth_count_5m`, `is_new_device`, `is_new_ip`.
3. **Neo4j Graph Features**: `shared_device_user_count`, `shared_ip_user_count`, `graph_risk_score`, `merchant_fraud_rate`.
4. **Behavioral Features**: `typing_speed_wpm`, `mouse_jitter_score`, `keystroke_anomaly_score`.

---

## 10. Decision Engine

The **Decision Engine** decouples machine learning probability estimation from business policy enforcement.

```mermaid
flowchart TD
    INPUT[Input: Fraud Probability + Unified Features + Graph Risk] --> RULES{Policy Rule Evaluation}
    
    RULES -->|Velocity 1m > 5 OR Hard Limit > $10,000| BLOCK[BLOCK: Auto Reject]
    RULES -->|Failed Auth >= 3 OR Shared Users >= 3| REVIEW[REVIEW: Route to SecOps Queue]
    RULES -->|New Device OR New IP Hopping| CHALLENGE[CHALLENGE: Trigger Step-Up 2FA]
    RULES -->|All Rules Clean| ML_EVAL{Evaluate ML Score}
    
    ML_EVAL -->|Score > 0.85| BLOCK
    ML_EVAL -->|0.65 < Score <= 0.85| REVIEW
    ML_EVAL -->|0.40 < Score <= 0.65| CHALLENGE
    ML_EVAL -->|Score <= 0.40| ALLOW[ALLOW: Immediate Approval]
```

### Policy Thresholds (Configured via `.env`)
- `DECISION_THRESHOLD_ALLOW=0.40`: Scores $\le 0.40$ approved immediately.
- `DECISION_THRESHOLD_CHALLENGE=0.65`: Scores in $(0.40, 0.65]$ require Step-Up 2FA / OTP verification.
- `DECISION_THRESHOLD_REVIEW=0.85`: Scores in $(0.65, 0.85]$ routed to fraud analyst queue.
- Scores $> 0.85$ are blocked automatically.

### Human-in-the-Loop Override
Analysts can manually override any AI decision via `POST /api/v1/decisions/{id}/override`. All overrides require a mandatory justification string and record the analyst's user ID in the audit log.

---

## 11. PostgreSQL / Neon Schema

Persistence is hosted on **Neon Cloud PostgreSQL** with strict foreign key constraints, indexes, and JSONB payload storage:

```mermaid
erDiagram
    users ||--o{ transactions : initiates
    users ||--o{ decisions : subject_of
    users ||--o{ alerts : generates
    users ||--o{ behavior_logs : tracks
    users ||--o{ audit_logs : performs
    transactions ||--|| decisions : results_in
    transactions ||--o{ alerts : triggers

    users {
        uuid id PK
        string email UK
        string full_name
        string hashed_password
        string role
        boolean is_active
        timestamp created_at
    }

    transactions {
        uuid id PK
        string transaction_ref UK
        uuid user_id FK
        float amount
        string currency
        string merchant_name
        string category
        string device_fingerprint
        string ip_address
        float fraud_score
        string risk_level
        boolean is_fraud
        jsonb metadata
        timestamp created_at
    }

    decisions {
        uuid id PK
        uuid transaction_id FK
        uuid user_id FK
        string decision
        float fraud_score
        string risk_level
        string triggered_rule
        string model_version
        boolean is_overridden
        string override_reason
        uuid overridden_by FK
        timestamp created_at
    }

    alerts {
        uuid id PK
        uuid transaction_id FK
        uuid user_id FK
        string alert_type
        string severity
        string status
        float risk_score
        text description
        timestamp created_at
    }
```

---

## 12. API Design

The API is fully documented via OpenAPI/Swagger at `/docs` and `/redoc`:

### Core Endpoints

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticate analyst & receive JWT access/refresh tokens |
| **Auth** | `POST` | `/api/v1/auth/register` | Register new platform operator (Admin only) |
| **Transactions** | `GET` | `/api/v1/transactions` | Paginated transaction listing with multi-field filtering |
| **Transactions** | `GET` | `/api/v1/transactions/{id}` | Detailed transaction inspection with PCA components |
| **Decisions** | `GET` | `/api/v1/decisions` | AI decision stream with filter by decision tier |
| **Decisions** | `POST` | `/api/v1/decisions/{id}/override` | Analyst manual decision override with audit trail |
| **Decisions** | `GET` | `/api/v1/decisions/rules/policy` | List active decision rules and configured thresholds |
| **Alerts** | `GET` | `/api/v1/alerts` | Paginated fraud alert queue |
| **Alerts** | `PATCH` | `/api/v1/alerts/{id}/status` | Update alert status (`INVESTIGATING`, `RESOLVED`, `DISMISSED`) |
| **Dashboard** | `GET` | `/api/v1/dashboard/stats` | KPI summary statistics (cached in Redis) |
| **Dashboard** | `GET` | `/api/v1/dashboard/trends` | 30-day transaction volume and fraud time-series |
| **Dashboard** | `GET` | `/api/v1/dashboard/risk-distribution`| Low / Medium / High risk tier breakdown |
| **Graph** | `GET` | `/api/v1/graph/users/{id}/cluster` | Query user entity graph cluster in Neo4j |
| **Feature Store**| `GET` | `/api/v1/feature-store/user/{id}` | Query real-time Redis hot features for a user |
| **Real-Time** | `WS` | `/api/v1/ws/events` | Bi-directional WebSocket stream for live UI updates |
| **Real-Time** | `GET` | `/api/v1/events/stream` | Server-Sent Events (SSE) fallback event stream |
| **Health** | `GET` | `/health` | Deep healthcheck verifying PostgreSQL, Redis, Neo4j, Kafka |

---

## 13. Docker Architecture

The complete system is containerized in `docker-compose.yml` with health checks, restart policies, and named persistent storage:

| Service Name | Container Name | Base Image | Port Mappings | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `redis` | `detexa_redis` | `redis:7-alpine` | `6379:6379` | Real-time feature store & caching |
| `neo4j` | `detexa_neo4j` | `neo4j:5.18.0-community` | `7474:7474`, `7687:7687` | Identity & syndicate graph database |
| `kafka` | `detexa_kafka` | `apache/kafka:3.7.0` | `9092:9092`, `29092:29092` | Event streaming broker (KRaft mode) |
| `flink-jobmanager`| `detexa_flink_jobmanager`| `flink:1.18.1-scala_2.12-java11`| `8081:8081` | Flink master & Web Dashboard |
| `flink-taskmanager`| `detexa_flink_taskmanager`| `flink:1.18.1-scala_2.12-java11`| — | Flink streaming worker slots |
| `backend` | `detexa_backend` | Python 3.11 Slim | `8000:8000` | FastAPI core backend & ML engine |
| `frontend` | `detexa_frontend` | Node.js 20 Alpine | `5173:5173` | React + TypeScript Vite preview |

- **Networking**: All services communicate across an internal bridge network `detexa_network`.
- **Persistent Volumes**: `redis_data`, `neo4j_data`, `neo4j_logs`, `kafka_data`, `flink_data`.

---

## 14. Environment Variables

All settings are managed via `.env` (configured in `backend/app/core/config.py`):

```bash
# ── Application & Runtime
APP_NAME=Detexa
APP_VERSION=2.0.0
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# ── Security & JWT
SECRET_KEY=778faf5b1c899317c3c1748aeccea95c3dd6553dd126cc1f344b9cade8de6f17
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Neon Cloud PostgreSQL
DATABASE_URL=postgresql://neondb_owner:npg_sample_pass@ep-shiny-pond-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_PRE_PING=true
DB_POOL_RECYCLE=1800

# ── Redis Real-Time Feature Store
REDIS_URL=redis://redis:6379/0
REDIS_ENABLED=true
REDIS_POOL_MAX_CONNECTIONS=50

# ── Neo4j Graph Database
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=detexa_neo4j_password
NEO4J_DATABASE=neo4j
NEO4J_ENABLED=true

# ── Apache Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TRANSACTIONS_TOPIC=detexa.transactions.raw
KAFKA_ALERTS_TOPIC=detexa.alerts.high_risk
KAFKA_CONSUMER_GROUP=detexa-fraud-engine-group
KAFKA_ENABLED=true

# ── Apache Flink
FLINK_JOBMANAGER_HOST=flink-jobmanager
FLINK_JOBMANAGER_PORT=8081

# ── Decision Engine Policy Thresholds
DECISION_THRESHOLD_ALLOW=0.40
DECISION_THRESHOLD_CHALLENGE=0.65
DECISION_THRESHOLD_REVIEW=0.85
RULE_MAX_VELOCITY_1M=5
RULE_MAX_VELOCITY_5M=12
RULE_MAX_FAILED_AUTH_5M=3
RULE_MAX_AMOUNT_DEVIATION=4.5
RULE_MAX_AMOUNT_HARD_LIMIT=10000.0
RULE_MAX_GRAPH_SHARED_USERS=3
RULE_MAX_GRAPH_RISK_SCORE=0.65
RULE_ENABLE_DEVICE_CHANGE_CHALLENGE=true
RULE_ENABLE_IP_HOPPING_CHALLENGE=true
RULE_OFF_PEAK_NIGHT_THRESHOLD=500.0

# ── Frontend API Gateway
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 15. How the Complete Transaction Flows Through Detexa

```mermaid
sequenceDiagram
    autonumber
    actor Client as User / POS Terminal
    participant API as FastAPI Ingestion
    participant Redis as Redis Feature Store
    participant Neo4j as Neo4j Graph
    participant ML as ML Inference Engine
    participant DE as Decision Engine
    participant DB as Neon PostgreSQL
    participant Kafka as Kafka Alert Topic
    participant RT as RealtimeBroadcaster
    participant UI as React Dashboard

    Client->>API: POST /api/v1/transactions
    
    par Parallel Feature Enrichment
        API->>Redis: Query 1m/5m Velocity, Device & IP History
        Redis-->>API: Return Hot Features
        API->>Neo4j: Query Shared Hardware & Degree Centrality
        Neo4j-->>API: Return Graph Risk Metrics
    end

    API->>ML: Pass 40-Dimensional Unified Feature Vector
    ML-->>API: Return Fraud Probability (e.g. 0.78)
    
    API->>DE: Arbitrate Score against Rules (Velocity, Graph, Hard Limit)
    DE-->>API: Output Final Decision: "REVIEW" (Reason: Score in Review Tier)

    API->>DB: Persist Transaction, DecisionLog, and Alert Record
    
    opt High Risk / Review
        API->>Kafka: Publish Alert Event to detexa.alerts.high_risk
    end

    API->>RT: Publish Transaction & Decision to Event Stream
    RT-->>UI: Push Event over WebSocket / SSE
    UI->>UI: Update Live Feed, Charts, and Alert Badge in Real Time

    API-->>Client: Return Transaction Confirmation & Decision Result
```

---

## 16. What Remains Incomplete

While all requested core functionalities and production resiliency layers are fully implemented, the following production-hardening items represent potential future architectural expansions:

1. **Multi-Node Distributed Kafka Cluster**: Kafka currently runs as a single-node KRaft broker suitable for single-host Docker environments; production enterprise clustering requires a multi-broker setup with replication factor $\ge 3$.
2. **PyFlink Auto-Job Submission Service**: Flink JobManager and TaskManager containers run and expose the Flink Web UI (`:8081`). Production auto-deployment currently relies on manual job submission or a custom sidecar container.
3. **Automated Continuous Model Retraining Loop**: The ML pipeline includes complete training and inference scripts, but lacks an automated continuous retraining cron job triggered by verified fraud labels.
4. **Live Payment Gateway Webhook Integrations**: Native webhook listeners for external payment processors (Stripe, Adyen, PayPal) can be added on top of the generic transaction ingestion API.

---

## 17. Known Limitations

1. **Single-Node Docker Compose Constraints**: Services share a single host machine's memory and CPU resources. Under massive simulated loads ($> 10,000\text{ tx/s}$), Docker container memory limits must be increased.
2. **Neo4j Community Edition Concurrency**: Neo4j Community Edition does not support multi-database clustering or enterprise role-based security out of the box.
3. **Cold-Start Graph Sparsity**: For brand-new users with zero transaction history, the graph intelligence component returns baseline risk ($0.0$) until shared device/IP relationships are observed.
4. **Browser Concurrency Limits on SSE**: Browsers typically limit concurrent HTTP/1.1 SSE connections to 6 per domain; the platform defaults to WebSockets to bypass this limitation.

---

## 18. Exact Commands Required to Start the System

### Option A: Complete Docker Compose Deployment (Recommended)

To build and start all 7 containers in the background:

```powershell
# 1. Navigate to the project root
cd "c:\Users\13ver\Desktop\New folder\project\Detexa"

# 2. Ensure your .env file is present (copy from .env.example if not created)
cp .env.example .env
cp .env.example backend/.env

# 3. Build and launch all containers
docker compose up --build -d

# 4. Verify all container health statuses
docker compose ps

# 5. View logs for the backend or streaming components
docker compose logs -f backend
```

**Service Access URLs:**
- **Frontend Dashboard**: `http://localhost:5173`
- **FastAPI Backend & Swagger Docs**: `http://localhost:8000/docs`
- **Apache Flink Web Dashboard**: `http://localhost:8081`
- **Neo4j Browser UI**: `http://localhost:7474` (User: `neo4j`, Password: `detexa_neo4j_password`)
- **Redis CLI**: `docker exec -it detexa_redis redis-cli`
- **Kafka Broker**: `localhost:9092` / `localhost:29092`

---

### Option B: Local Developer Mode (Host Services)

If running services directly on the host machine:

#### Step 1: Start Supporting Infrastructure
```powershell
docker compose up redis neo4j kafka flink-jobmanager flink-taskmanager -d
```

#### Step 2: Start FastAPI Backend
```powershell
cd "c:\Users\13ver\Desktop\New folder\project\Detexa\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Step 3: Start React Frontend
```powershell
cd "c:\Users\13ver\Desktop\New folder\project\Detexa\frontend"
npm install
npm run dev
```

---

### Verification & Healthcheck Command

To verify complete end-to-end system health across all backing stores:

```powershell
curl http://localhost:8000/health
```

Expected Output:
```json
{
  "status": "healthy",
  "app_name": "Detexa",
  "version": "2.0.0",
  "environment": "production",
  "services": {
    "database": {
      "status": "healthy",
      "engine": "postgresql",
      "dialect": "neon"
    },
    "redis": {
      "status": "healthy",
      "connected_clients": 2
    },
    "neo4j": {
      "status": "healthy",
      "version": "5.18.0"
    },
    "kafka": {
      "status": "healthy",
      "bootstrap_servers": "kafka:9092"
    }
  }
}
```
