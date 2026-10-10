# Detexa System Architecture

This document provides a comprehensive technical breakdown of the Detexa architecture, detailing how distributed streaming, machine learning, in-memory caching, graph analytics, and real-time frontend visualization integrate to deliver sub-millisecond banking fraud prevention.

---

## 1. Overall System Architecture

Detexa utilizes a modern **event-driven, lambda-inspired microservices architecture** optimized for low latency, high throughput, and explainable decisioning.

```
                                  ┌─────────────────────────────────────────┐
                                  │           React 18 + TS UI              │
                                  │      (Dark/Light 4-Color Palette)       │
                                  └───────────────▲─────────────────────────┘
                                                  │ (HTTP / WebSocket / SSE)
                                                  │
┌──────────────────────┐                  ┌───────▼─────────────────────────┐
│ Banking Core / Ingest│ ───────────────> │         FastAPI Gateway         │
└──────────────────────┘                  └───────┬─────────────────────────┘
                                                  │
                                  ┌───────────────┴───────────────┐
                                  │                               │
                                  ▼ (Produce)                     ▼ (Async Tasks)
                      ┌───────────────────────┐       ┌───────────────────────┐
                      │     Apache Kafka      │       │    PostgreSQL/Neon    │
                      │  (transactions.raw)   │       │  (Relational Storage) │
                      └───────────┬───────────┘       └───────────────────────┘
                                  │
                                  ▼ (Consume)
                      ┌───────────────────────┐
                      │     Apache Flink      │
                      │  (Sliding Window Agg) │
                      └───────────┬───────────┘
                                  │
                                  ▼ (Enrich & Write)
                      ┌───────────────────────┐       ┌───────────────────────┐
                      │      Redis Cache      │       │      Neo4j Graph      │
                      │   (Hot Feature Store) │       │   (Entity Resolution) │
                      └───────────┬───────────┘       └───────────┬───────────┘
                                  │                               │
                                  └───────────────┬───────────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │   ML & Decision Engine│
                                      │  (XGBoost + TreeSHAP) │
                                      └───────────┬───────────┘
                                                  │
                                                  ▼ (Broadcast)
                                      ┌───────────────────────┐
                                      │  Realtime Broadcaster │
                                      │    (SSE & WebSocket)  │
                                      └───────────────────────┘
```

---

## 2. Core Architectural Components & Rationale

### 2.1 FastAPI Gateway & Core API
- **Technology:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Uvicorn (ASGI).
- **Purpose:** High-performance RESTful API gateway serving transaction ingestion, prediction endpoints, security alerts, and system health checks.
- **Auth Performance Optimization:** Validated user auth profiles are cached in Redis (`auth:user:{user_id}`) with a 60-second TTL to avoid WAN database roundtrips during JWT authentication while preserving cryptographic token verification.
- **Why it exists:** FastAPI leverages Python asynchronous programming (`async/await`) and native C-speed Pydantic validation, offering sub-millisecond request serialization and automatic OpenAPI documentation.

### 2.2 Apache Kafka (Message Broker)
- **Technology:** Apache Kafka with Zookeeper coordination.
- **Purpose:** Distributed, fault-tolerant message bus decoupling transaction producers from downstream analytics and stream workers.
- **Topics:**
  - `transactions.raw`: Ingested raw transactions published by clients.
  - `transactions.enriched`: Transactions enriched with temporal and client metadata.
  - `fraud.alerts`: High-priority incident events dispatched to alert handlers.
  - `metrics.stream`: Aggregated throughput, latency, and fraud metrics.
- **Why it exists:** Provides guaranteed durability, high-throughput buffering, and replayability under heavy traffic spikes without overloading downstream databases.

### 2.3 Apache Flink (Stream Processing Engine)
- **Technology:** Apache Flink (JobManager & TaskManager).
- **Purpose:** Stateful event-time streaming analytics and sliding window calculations.
- **Why it exists:** Calculates rolling velocity and amount sums (e.g. 1m burst, 5m totals) across unbounded transaction streams with exactly-once processing semantics.

### 2.4 Redis (Hot Real-Time Feature Store)
- **Technology:** Redis in-memory key-value database.
- **Purpose:** Sub-2ms low-latency feature retrieval for real-time model inference.
- **Keyspace Design:**
  - `user:{user_id}:velocity:{window}`: Transaction count in sliding interval with TTL expiration.
  - `user:{user_id}:amount_sum:{window}`: Sum of transaction amounts over rolling window.
  - `user:{user_id}:failed_auth:{window}`: Consecutive failed authentication/PIN attempts.
  - `user:{user_id}:devices:24h`: Redis HyperLogLog / Set of distinct hardware fingerprints seen in 24 hours.
- **Why it exists:** Relational databases are too slow for real-time aggregation queries during transactional checkout paths; Redis delivers instant in-memory lookups.

### 2.5 Entity Resolution & Link Analysis (Redis Sets & PostgreSQL)
- **Technology:** Redis In-Memory Sets (`device:{fp}:users`, `ip:{address}:users`) and PostgreSQL Relational Linkage (`devices`, `ip_addresses`, `transactions`).
- **Purpose:** Sub-millisecond entity resolution, multi-account device sharing, and collusion ring detection without heavy graph database overhead.
- **Architectural Audit Finding:** As documented in [`docs/NEO4J_AUDIT.md`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/docs/NEO4J_AUDIT.md), Neo4j Community Edition introduced 1.2 GB RAM overhead and 5–20 ms Bolt query latency while performing degree-counting queries that are identical to Redis Set cardinalities (`SCARD`) and PostgreSQL indexed queries.
- **Streamlined Entity Resolution:**
  - **Device Sharing:** Redis `SADD device:{device_fp}:users {user_id}` allows $O(1)$ $<0.2\text{ ms}$ evaluation of shared hardware collusion rings.
  - **Relational Integrity:** PostgreSQL indexed foreign keys join `transactions` $\rightarrow$ `devices` $\rightarrow$ `users` for deep historical audits without dual-write consistency failure modes.

### 2.6 Machine Learning Models & Inference Pipeline
- **Credit Fraud Model (XGBoost):**
  - **Artifacts:** `models/credit_fraud_xgboost.joblib`, `models/credit_fraud_scaler.joblib`.
  - **Algorithm:** Gradient boosted decision trees trained on normalized transaction data with cost-sensitive weighting.
  - **Explainability:** Real-time TreeSHAP calculates feature attribution scores ($S_i$) per prediction.
- **Behavioral Anomaly Model (Isolation Forest):**
  - **Artifacts:** `models/behavior_isolation_forest.joblib`, `models/behavior_scaler.joblib`.
  - **Algorithm:** Unsupervised decision forest detecting anomalous typing speed, mouse velocity, session duration, and network proxy combinations.
- **Singleton Lifecycle:** Pre-loaded into memory during application startup (`lifespan` handler) for instantaneous inference without file I/O overhead.

---

## 3. Canonical 61-Feature Schema

Every transaction is transformed into a standardized 61-feature vector across 5 domains before scoring:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CANONICAL 61-FEATURE SCHEMA VECTOR                   │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Domain                  │ Features Included                            │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 1. Transaction Raw      │ amount, amount_log1p, currency_usd_eq,       │
│    (6 features)         │ hour_of_day, day_of_week, is_weekend         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 2. Temporal & Cyclical  │ hour_sin, hour_cos, day_sin, day_cos,        │
│    (6 features)         │ month_sin, month_cos                         │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 3. Behavioral & Client  │ is_vpn, is_tor, typing_speed_wpm,            │
│    (11 features)        │ mouse_velocity, failed_logins_recent,        │
│                         │ device_trust_score, ip_reputation_score,     │
│                         │ geo_distance_km, impossible_speed_flag,      │
│                         │ user_agent_risk, session_duration_s          │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 4. Redis Hot Velocities │ velocity_1m, 5m, 15m, 1h, 24h;               │
│    (22 features)        │ amount_sum_1m, 5m, 15m, 1h, 24h;             │
│                         │ amount_avg_1h, amount_max_24h,               │
│                         │ failed_auth_count_5m, failed_auth_count_1h;  │
│                         │ distinct_merchants_24h, distinct_devices_24h │
├─────────────────────────┼──────────────────────────────────────────────┤
│ 5. Neo4j Graph Risk     │ shared_device_user_count, shared_ip_count,   │
│    (16 features)        │ fraud_ring_size, graph_risk_score,           │
│                         │ direct_fraud_connection, page_rank_score,    │
│                         │ betweenness_centrality, degree_centrality    │
└─────────────────────────┴──────────────────────────────────────────────┘
```

---

## 4. Decision Engine & Arbitration

The Decision Engine sits between ML probability estimation and core banking execution. It resolves final verdicts using score bands combined with deterministic risk policies:

```
                  ┌───────────────────────────────┐
                  │   ML Fraud Probability Score  │
                  └───────────────┬───────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
    Score ≤ 0.30            0.30 < Score ≤ 0.70     0.70 < Score ≤ 0.90
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│      ALLOW       │    │    CHALLENGE     │    │      REVIEW      │
│ (Zero Friction)  │    │ (Step-Up 2FA/MFA)│    │ (Analyst Triage) │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                                          │
                                                          ▼ Score > 0.90
                                                ┌──────────────────┐
                                                │      BLOCK       │
                                                │ (Hard Rejection) │
                                                └──────────────────┘
```

### Deterministic Rule Policies:
- **`RULE_VELOCITY`:** Triggered if 1-minute velocity $> 3$ or 5-minute velocity $> 8$. Outcome: `BLOCK`.
- **`RULE_AUTH_FAIL`:** Triggered if $> 3$ PIN/CVV failures occur in 5 minutes. Outcome: `CHALLENGE`.
- **`RULE_DEVICE_HOP`:** Triggered when a new, unverified device fingerprint transacts. Outcome: `CHALLENGE`.
- **`RULE_GRAPH_COLLUSION`:** Triggered when hardware is shared with $\ge 3$ confirmed fraudulent accounts. Outcome: `BLOCK`.
- **`RULE_HIGH_VALUE`:** Triggered when transaction amount exceeds authorization bounds. Outcome: `REVIEW`.

---

## 5. Relational Database Schema (PostgreSQL/Neon)

Managed via idempotent Alembic migrations (`backend/alembic/versions/0001_initial_neon_schema.py`):

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│      users       │       │    merchants     │       │     devices      │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (UUID, PK)    │       │ id (VARCHAR, PK) │       │ id (UUID, PK)    │
│ email (VARCHAR)  │       │ name (VARCHAR)   │       │ device_fp (TEXT) │
│ hashed_pw (TEXT) │       │ category (TEXT)  │       │ is_trusted (BOOL)│
└────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
         │                          │                          │
         │                          │                          │
         └─────────────────┐        │        ┌─────────────────┘
                           ▼        ▼        ▼
                      ┌────────────────────────────┐
                      │        transactions        │
                      ├────────────────────────────┤
                      │ id (VARCHAR, PK)           │
                      │ transaction_ref (VARCHAR)  │
                      │ user_id (UUID, FK)         │
                      │ merchant_id (VARCHAR, FK)  │
                      │ device_id (UUID, FK)       │
                      │ amount (NUMERIC)           │
                      │ currency (VARCHAR)         │
                      │ timestamp (TIMESTAMP)      │
                      │ is_fraud (BOOLEAN)         │
                      └─────────────┬──────────────┘
                                    │
                                    ├──────────────────────────┐
                                    ▼                          ▼
                      ┌──────────────────────────┐   ┌───────────────────┐
                      │    fraud_predictions     │   │      alerts       │
                      ├──────────────────────────┤   ├───────────────────┤
                      │ id (UUID, PK)            │   │ id (VARCHAR, PK)  │
                      │ transaction_id (FK)      │   │ transaction_id(FK)│
                      │ fraud_score (FLOAT)      │   │ risk_level (ENUM) │
                      │ decision (ENUM)          │   │ status (ENUM)     │
                      │ risk_level (ENUM)        │   │ score (FLOAT)     │
                      │ latency_ms (FLOAT)       │   │ description (TEXT)│
                      │ shap_values (JSONB)      │   │ shap_values(JSONB)│
                      └──────────────────────────┘   └───────────────────┘
```

---

## 6. Real-Time Streaming & Broadcaster

Detexa provides real-time updates to web clients without polling:
1. **Server-Sent Events (SSE):** `GET /api/v1/realtime/stream` distributes continuous live updates across topics:
   - `transaction_created`: Real-time transaction stream.
   - `fraud_alert`: Incident generation events.
   - `metrics_tick`: High-level throughput, average score, and blocked ratios.
2. **WebSockets:**
   - `/ws/transactions`: Bidirectional event streaming for rapid live feeds.
   - `/ws/alerts`: Live push for high-priority security notifications.
3. **Broadcaster Engine:** `app/core/realtime_broadcaster.py` utilizes asynchronous event queues and thread-safe dispatches to ensure seamless event broadcasting across concurrent web clients.

---

## 7. Frontend UI & Strict 4-Color Theme System

- **Framework:** React 18, TypeScript, Tailwind CSS, Vite.
- **Theme Architecture:** Single source of truth via `ThemeContext.tsx`, persisted in `localStorage` under `detexa_theme`, with an inline head script in `index.html` preventing theme flash on load.
- **Strict 4-Color Constraint:**
  - **White (`#ffffff`) & Black (`#000000`):** Surfaces, cards, text, and structure.
  - **Blue (`#2563eb`, `#3b82f6`):** Primary interactions, links, `ALLOW`, `CHALLENGE`, and normal transaction streams.
  - **Red (`#dc2626`, `#ef4444`):** Fraud detection, `BLOCK`, `REVIEW`, high-risk alerts, and critical anomalies.
  - Opacities (e.g. `bg-blue-600/10`, `border-black/10`) provide visual depth without introducing extra hues.
