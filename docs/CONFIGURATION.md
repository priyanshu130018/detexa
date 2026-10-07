# ⚙️ Detexa — Centralized Configuration Guide

> **Version:** 2.0.0  
> **Module Location:** `backend/app/core/config.py` & `frontend/.env`  
> **Specification:** Pydantic Settings v2 + Vite Client Environment  

---

## 📋 Table of Contents
1. [Architecture & Design Principles](#1-architecture--design-principles)
2. [Backend Configuration (`backend/.env`)](#2-backend-configuration-backendenv)
   - [2.1 Application & Runtime Settings](#21-application--runtime-settings)
   - [2.2 API Server & Routing](#22-api-server--routing)
   - [2.3 CORS (Cross-Origin Resource Sharing)](#23-cors-cross-origin-resource-sharing)
   - [2.4 Security & JWT Settings](#24-security--jwt-settings)
   - [2.5 Relational Database (PostgreSQL / Neon Cloud)](#25-relational-database-postgresql--neon-cloud)
   - [2.6 Redis In-Memory Cache](#26-redis-in-memory-cache)
   - [2.7 Kafka Distributed Event Streaming](#27-kafka-distributed-event-streaming)
   - [2.8 Neo4j Graph Database](#28-neo4j-graph-database)
   - [2.9 Machine Learning & Inference Thresholds](#29-machine-learning--inference-thresholds)
3. [Frontend Configuration (`frontend/.env`)](#3-frontend-configuration-frontendenv)
4. [Environment Setup & Production Best Practices](#4-environment-setup--production-best-practices)

---

## 1. Architecture & Design Principles

Detexa uses **Pydantic Settings v2** to centralize and validate all backend configuration parameters at application startup.

### Key Tenets:
- **Zero Hardcoded Secrets:** No secrets, database passwords, or hostnames are embedded in source code.
- **Strict Typing & Validation:** All environment variables are validated into strict Python types (`int`, `float`, `bool`, `List[str]`, `Literal`).
- **Graceful Fallbacks:** Cloud backends like Redis, Kafka, and Neo4j feature toggle flags (`*_ENABLED`) and fallback mechanisms to prevent server crashes if external services are unconfigured during local development.
- **Cloud-Ready Placeholders:** Out-of-the-box support and placeholders for **Neon Serverless PostgreSQL**, **Upstash / Redis Cloud**, **Confluent / Kafka**, and **Neo4j AuraDB**.

---

## 2. Backend Configuration (`backend/.env`)

### 2.1 Application & Runtime Settings

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | `str` | `Detexa` | Brand name displayed across API docs and log outputs. |
| `APP_VERSION` | `str` | `2.0.0` | Semantic version string of the platform. |
| `APP_ENV` | `str` | `development` | Environment mode: `development`, `staging`, `production`, `testing`. |
| `DEBUG` | `bool` | `false` | When `true`, enables verbose tracebacks in API error responses. |
| `LOG_LEVEL` | `str` | `INFO` | Minimum severity level logged: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_FILE_PATH` | `str` | `logs/detexa.log` | Path for disk-based structured log sink. |
| `LOG_ROTATION` | `str` | `10 MB` | File size threshold triggering log rotation. |
| `LOG_RETENTION` | `str` | `30 days` | Duration before rotated logs are deleted. |

---

### 2.2 API Server & Routing

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `API_HOST` | `str` | `0.0.0.0` | Network interface address bound by the Uvicorn ASGI server. |
| `API_PORT` | `int` | `8000` | Port on which the FastAPI application listens. |
| `API_V1_STR` | `str` | `/api/v1` | URL path prefix for all Version 1 REST API routers. |
| `DOCS_URL` | `str` | `/docs` | Path to the interactive Swagger UI (set to `None` to disable in production). |
| `REDOC_URL` | `str` | `/redoc` | Path to the ReDoc API documentation. |

---

### 2.3 CORS (Cross-Origin Resource Sharing)

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `CORS_ORIGINS` | `List[str]` / JSON | `["http://localhost:5173", ...]` | Allowed client origin URLs. Can be specified as a JSON array or comma-separated list. |
| `CORS_ALLOW_CREDENTIALS` | `bool` | `true` | Allows cookies and Authorization headers across CORS requests. |

---

### 2.4 Security & JWT Settings

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | `str` | *(random 32-char hex)* | Cryptographic HMAC secret key used to sign and verify JWT tokens. |
| `ALGORITHM` | `str` | `HS256` | JWT signing algorithm. Standard: `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `120` | Lifetime of issued JWT access tokens before expiration. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `7` | Lifetime of refresh token grants. |

---

### 2.5 Relational Database (PostgreSQL / Neon Cloud)

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `str` | `postgresql://detexa_user:detexa_pass@localhost:5432/detexa_db` | SQLAlchemy connection URI. Supports local PostgreSQL, SQLite (`sqlite:///./test.db`), or cloud Neon. |
| `DB_POOL_SIZE` | `int` | `10` | Base number of active connections in the connection pool. |
| `DB_MAX_OVERFLOW` | `int` | `20` | Maximum surge connections permitted beyond `DB_POOL_SIZE`. |
| `DB_POOL_PRE_PING` | `bool` | `true` | Tests connection liveness before checking out from pool (essential for serverless DBs). |
| `DB_POOL_RECYCLE` | `int` | `1800` | Recycles pool connections after N seconds to prevent stale timeouts. |
| `DB_ECHO` | `bool` | `false` | If `true`, logs raw SQL queries generated by SQLAlchemy to stdout. |

#### Neon Serverless PostgreSQL Example:
```env
DATABASE_URL=postgresql://neondb_owner:npg_abcdef123456@ep-sample-pool-123456.us-east-2.aws.neon.tech/detexa?sslmode=require
```

---

### 2.6 Redis In-Memory Cache & Real-Time Feature Store

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Connection URI for Redis. Use `rediss://` for TLS-enabled cloud instances. |
| `REDIS_ENABLED` | `bool` | `true` | Global switch to enable or bypass caching and feature store. |
| `REDIS_PASSWORD` | `str` | `None` | Optional password if not provided inside `REDIS_URL`. |
| `REDIS_SSL` | `bool` | `false` | Forces TLS/SSL encryption on Redis sockets. |
| `REDIS_POOL_MAX_CONNECTIONS` | `int` | `50` | Maximum connections in Redis thread-safe connection pool. |
| `REDIS_SOCKET_TIMEOUT` | `float` | `2.0` | Socket read/write timeout in seconds. |
| `REDIS_SOCKET_CONNECT_TIMEOUT`| `float` | `2.0` | Socket connection establishment timeout in seconds. |
| `REDIS_CACHE_TTL_STATS` | `int` | `30` | Cache time-to-live (seconds) for `/alerts/stats` dashboard metrics. |
| `REDIS_CACHE_TTL_PREDICTIONS`| `int` | `300` | Cache time-to-live (seconds) for prediction deduplication lookups. |
| `REDIS_FS_TTL_TRANSACTIONS_SEC`| `int` | `86400` | Feature Store: Sliding window transaction TTL (24 hours). |
| `REDIS_FS_TTL_FAILURES_SEC` | `int` | `3600` | Feature Store: Failed authentication/decline events TTL (1 hour). |
| `REDIS_FS_TTL_DEVICES_SEC` | `int` | `86400` | Feature Store: Recent device fingerprint set TTL (24 hours). |
| `REDIS_FS_TTL_IPS_SEC` | `int` | `86400` | Feature Store: Recent IP address set TTL (24 hours). |
| `REDIS_FS_TTL_MERCHANTS_SEC` | `int` | `3600` | Feature Store: Recent merchant diversity set TTL (1 hour). |
| `REDIS_FS_TTL_COUNTERS_SEC` | `int` | `604800` | Feature Store: Behavioral risk and frequency counters TTL (7 days). |


#### Upstash / Cloud Redis Example:
```env
REDIS_URL=rediss://default:your-upstash-token@sample-endpoint.upstash.io:6379
REDIS_SSL=true
```

---

### 2.7 Kafka Distributed Event Streaming

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `KAFKA_BOOTSTRAP_SERVERS` | `str` | `localhost:9092` | Comma-separated list of Kafka broker endpoints. |
| `KAFKA_SECURITY_PROTOCOL` | `str` | `PLAINTEXT` | Transport protocol: `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL`. |
| `KAFKA_SASL_MECHANISM` | `str` | `PLAIN` | SASL auth mechanism: `PLAIN`, `SCRAM-SHA-256`, `SCRAM-SHA-512`. |
| `KAFKA_SASL_USERNAME` | `str` | `None` | SASL username / API key for Kafka clusters. |
| `KAFKA_SASL_PASSWORD` | `str` | `None` | SASL password / API secret for Kafka clusters. |
| `KAFKA_TRANSACTIONS_TOPIC` | `str` | `detexa.transactions.raw` | Ingestion topic name for real-time transaction streams. |
| `KAFKA_ALERTS_TOPIC` | `str` | `detexa.alerts.high_risk` | Egress topic name for broadcasted fraud alerts. |
| `KAFKA_CONSUMER_GROUP` | `str` | `detexa-fraud-engine-group` | Consumer group identifier for load-balanced partition consumption. |
| `KAFKA_CLIENT_ID` | `str` | `detexa-backend-v2` | Identification string sent with client requests. |
| `KAFKA_ENABLED` | `bool` | `false` | Enables background Kafka producers and consumers. |

#### Confluent Cloud Kafka Example:
```env
KAFKA_BOOTSTRAP_SERVERS=pkc-xyz.us-east-2.aws.confluent.cloud:9092
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=YOUR_CONFLUENT_API_KEY
KAFKA_SASL_PASSWORD=YOUR_CONFLUENT_API_SECRET
KAFKA_ENABLED=true
```

---

### 2.8 Neo4j Graph Database

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `NEO4J_URI` | `str` | `bolt://localhost:7687` | Connection URI (`bolt://`, `neo4j://`, or `neo4j+s://` for AuraDB). |
| `NEO4J_USER` | `str` | `neo4j` | Database user for Cypher graph queries. |
| `NEO4J_PASSWORD` | `str` | `neo4j_password_placeholder` | Password for Neo4j authentication. |
| `NEO4J_DATABASE` | `str` | `neo4j` | Target graph database instance name. |
| `NEO4J_ENABLED` | `bool` | `false` | Enables graph traversal and fraud ring cluster analysis. |

#### Neo4j AuraDB Example:
```env
NEO4J_URI=neo4j+s://12345678.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-auradb-generated-password
NEO4J_ENABLED=true
```

---

### 2.9 Machine Learning & Inference Thresholds

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `MODEL_PATH` | `str` | `app/ml/saved` | Directory containing serialized `.pkl` pipelines. |
| `CREDIT_MODEL_FILENAME` | `str` | `credit_fraud_pipeline.pkl` | Serialized credit fraud pipeline filename. |
| `BEHAVIOR_MODEL_FILENAME` | `str` | `behavior_pipeline.pkl` | Serialized behavioral anomaly pipeline filename. |
| `FRAUD_THRESHOLD` | `float` | `0.50` | Probability cutoff triggering `Medium` risk and fraud flagging. |
| `HIGH_RISK_THRESHOLD` | `float` | `0.75` | Probability cutoff triggering `High` risk and immediate escalation. |
| `BATCH_INFERENCE_MAX_ROWS` | `int` | `5000` | Maximum rows permitted per batch CSV scoring request. |
| `SHAP_TOP_K_FEATURES` | `int` | `10` | Number of top feature contribution scores computed per transaction. |

---

## 3. Frontend Configuration (`frontend/.env`)

The React + Vite frontend accesses environment variables prefixed with `VITE_`:

| Variable Name | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `str` | `http://localhost:8000/api/v1` | Base URL of the backend REST API gateway. |
| `VITE_APP_NAME` | `str` | `Detexa` | Display name rendered in the UI navigation. |
| `VITE_APP_VERSION` | `str` | `2.0.0` | Frontend build version tag. |
| `VITE_ENABLE_AUTO_REFRESH` | `bool` | `true` | Allows periodic polling for new alerts and telemetry updates. |
| `VITE_AUTO_REFRESH_INTERVAL_MS`| `int` | `15000` | Polling interval in milliseconds for overview metrics. |
| `VITE_DEFAULT_PAGE_SIZE` | `int` | `50` | Default row limit for transaction and alert tables. |

---

## 4. Environment Setup & Production Best Practices

1. **Initial Setup:**
   ```bash
   # Backend
   cd backend
   cp .env.example .env
   
   # Frontend
   cd ../frontend
   cp .env.example .env
   ```

2. **Secret Generation:**
   Generate a cryptographic 256-bit random key for `SECRET_KEY`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Security Checklist for Production Deployment:**
   - Set `APP_ENV=production` and `DEBUG=false`.
   - Update `SECRET_KEY` to a unique 32+ character random string.
   - Restrict `CORS_ORIGINS` to trusted domains only.
   - Provide valid cloud connection strings for `DATABASE_URL` (with `sslmode=require`) and `REDIS_URL`.
   - Ensure file permissions on `.env` restrict read access to the application process user (`chmod 600 .env`).

---
*Documentation maintained for Detexa Platform v2.0.0.*
