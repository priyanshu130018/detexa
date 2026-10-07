# Detexa Neon PostgreSQL Database Architecture & Schema Design

## 1. Architectural Overview

Detexa is engineered with a fully normalized, relational schema designed for **Neon PostgreSQL Serverless** and standard PostgreSQL 15+. The schema adheres to Third Normal Form (3NF) while preserving optimal read performance for high-throughput fraud inference, transactional search, security triage, and behavioral analytics.

### Neon Serverless Database Considerations
- **Connection Pooling**: Uses SQLAlchemy connection pooling (`pool_size=10`, `max_overflow=20`, `pool_recycle=1800`, `pool_pre_ping=True`) designed for Neon's autosuspend architecture.
- **Data Types**: Native PostgreSQL `UUID` (`uuid-ossp` or SQLAlchemy `PG_UUID`), native `JSONB` for SHAP feature importances and audit logs, and native `ENUM` types for constrained status/risk categorizations.
- **Production Migrations**: `Base.metadata.create_all()` is strictly prevented in production environments; all schema changes are managed via version-controlled **Alembic migrations**.

```
                           ┌─────────────────┐
                           │      users      │
                           └────────┬────────┘
                                    │
         ┌──────────────────────────┼─────────────────────────┐
         │ 1:N                      │ 1:N                     │ 1:N
┌────────▼────────┐        ┌────────▼────────┐       ┌────────▼────────┐
│     devices     │        │  transactions   │       │   audit_logs    │
└────────┬────────┘        └────────┬────────┘       └─────────────────┘
         │                          │
         │                          │ 1:1
         │                 ┌────────▼────────┐
         │                 │fraud_predictions│
         │                 └────────┬────────┘
         │                          │ 1:1
         │                 ┌────────▼────────┐
         │                 │  fraud_alerts   │
         │                 └─────────────────┘
         │                          ▲
         │                          │
┌────────▼────────┐        ┌────────┴────────┐
│  behavior_logs  ├────────►  ip_addresses   │
└─────────────────┘        └─────────────────┘
         ▲                          ▲
         │                          │
         └─────────[merchants]──────┘
```

---

## 2. Normalized Tables & Entity Relationships

The schema consists of **10 normalized tables**:

### 1. `users`
Identity, credentials, and access control.
- `id` (UUID, PK)
- `name` (VARCHAR(120), NOT NULL)
- `email` (VARCHAR(255), UNIQUE, NOT NULL, INDEX)
- `mobile` (VARCHAR(20), NULLABLE)
- `hashed_password` (VARCHAR(255), NOT NULL)
- `is_active` (BOOLEAN, DEFAULT TRUE)
- `is_admin` (BOOLEAN, DEFAULT FALSE)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW)
- `last_login` (TIMESTAMPTZ, NULLABLE)

### 2. `merchants`
Normalized merchant directory with category and risk profiling.
- `id` (UUID, PK)
- `name` (VARCHAR(150), UNIQUE, NOT NULL, INDEX)
- `category` (VARCHAR(60), NOT NULL, INDEX)
- `risk_score` (FLOAT, DEFAULT 0.0)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW)

### 3. `devices`
Device telemetry, user agents, and trust fingerprints.
- `id` (UUID, PK)
- `user_id` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `device_fingerprint` (VARCHAR(255), NOT NULL, INDEX)
- `user_agent` (TEXT, NULLABLE)
- `is_trusted` (BOOLEAN, DEFAULT TRUE)
- `first_seen_at` (TIMESTAMPTZ, DEFAULT NOW)
- `last_seen_at` (TIMESTAMPTZ, DEFAULT NOW)
- **Constraint**: `UniqueConstraint("user_id", "device_fingerprint")`

### 4. `ip_addresses`
IP reputation, geo-location, and proxy/TOR telemetry.
- `id` (UUID, PK)
- `ip_address` (VARCHAR(45), UNIQUE, NOT NULL, INDEX)
- `geo_country` (VARCHAR(60), NULLABLE, INDEX)
- `geo_city` (VARCHAR(60), NULLABLE)
- `is_vpn` (BOOLEAN, DEFAULT FALSE)
- `is_tor` (BOOLEAN, DEFAULT FALSE)
- `reputation_score` (FLOAT, DEFAULT 0.0)
- `last_checked_at` (TIMESTAMPTZ, DEFAULT NOW)

### 5. `transactions`
Core financial transactions with Kaggle PCA features ($V_1..V_{28}$) and foreign keys to normalized entities.
- `id` (UUID, PK)
- `user_id` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `merchant_id` (UUID, FK -> `merchants.id` ON DELETE SET NULL, INDEX)
- `device_id` (UUID, FK -> `devices.id` ON DELETE SET NULL, INDEX)
- `ip_id` (UUID, FK -> `ip_addresses.id` ON DELETE SET NULL, INDEX)
- `transaction_ref` (VARCHAR(64), UNIQUE, NOT NULL, INDEX)
- `amount` (FLOAT, NOT NULL)
- `currency` (VARCHAR(10), DEFAULT 'USD')
- `merchant` (VARCHAR(120), NULLABLE) — *Denormalized for instant display*
- `category` (VARCHAR(60), NULLABLE)
- `country` (VARCHAR(60), NULLABLE)
- `v1` .. `v28` (FLOAT, NULLABLE) — Kaggle PCA components
- `fraud_score` (FLOAT, NULLABLE)
- `risk_level` (ENUM `risklevel`: `LOW`, `MEDIUM`, `HIGH`, INDEX)
- `is_fraud` (BOOLEAN, DEFAULT FALSE, INDEX)
- `label` (INTEGER, NULLABLE)
- `timestamp` (TIMESTAMPTZ, DEFAULT NOW, INDEX)
- **Constraints & Indexes**:
  - `CheckConstraint("amount > 0")`
  - `Index("ix_transactions_user_timestamp", "user_id", "timestamp")`
  - `Index("ix_transactions_fraud_timestamp", "is_fraud", "timestamp")`

### 6. `model_metadata`
Machine learning model registry tracking versions, architectures, and evaluation metrics.
- `id` (UUID, PK)
- `model_name` (VARCHAR(100), NOT NULL, INDEX)
- `version` (VARCHAR(30), NOT NULL)
- `algorithm` (VARCHAR(60), NOT NULL)
- `threshold` (FLOAT, DEFAULT 0.50)
- `is_active` (BOOLEAN, DEFAULT TRUE)
- `metrics` (JSONB / JSON, NULLABLE)
- `trained_at` (TIMESTAMPTZ, DEFAULT NOW)
- **Constraint**: `UniqueConstraint("model_name", "version")`

### 7. `fraud_predictions`
Inference audit records, decision verdicts (`ALLOW`, `REVIEW`, `BLOCK`), and SHAP feature importances.
- `id` (UUID, PK)
- `transaction_id` (UUID, FK -> `transactions.id` ON DELETE CASCADE, UNIQUE, INDEX)
- `model_id` (UUID, FK -> `model_metadata.id` ON DELETE SET NULL, INDEX)
- `endpoint` (VARCHAR(60), NOT NULL)
- `input_hash` (VARCHAR(64), NULLABLE, INDEX)
- `fraud_score` (FLOAT, NOT NULL)
- `anomaly_score` (FLOAT, NULLABLE)
- `risk_level` (ENUM `risklevel`, INDEX)
- `is_fraud` (BOOLEAN, DEFAULT FALSE)
- `decision` (ENUM `decisiontype`: `ALLOW`, `REVIEW`, `BLOCK`, NOT NULL)
- `shap_values` (JSONB / JSON, NULLABLE)
- `latency_ms` (FLOAT, NOT NULL)
- `model_version` (VARCHAR(30), NOT NULL)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW, INDEX)
- **Constraint**: `CheckConstraint("fraud_score >= 0.0 AND fraud_score <= 1.0")`

### 8. `fraud_alerts`
Security incident triage entity.
- `id` (UUID, PK)
- `user_id` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `transaction_id` (UUID, FK -> `transactions.id` ON DELETE SET NULL, INDEX)
- `prediction_id` (UUID, FK -> `fraud_predictions.id` ON DELETE SET NULL, INDEX)
- `assigned_to` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `alert_type` (VARCHAR(60), NOT NULL)
- `risk_level` (ENUM `risklevel`, INDEX)
- `score` (FLOAT, NOT NULL)
- `description` (TEXT, NOT NULL)
- `status` (ENUM `alertstatus`: `open`, `reviewed`, `resolved`, `false_positive`, INDEX)
- `resolution_notes` (TEXT, NULLABLE)
- `shap_values` (JSONB / JSON, NULLABLE)
- `metadata` (JSONB / JSON, NULLABLE)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW, INDEX)
- `resolved_at` (TIMESTAMPTZ, NULLABLE)
- **Index**: `Index("ix_fraud_alerts_status_risk_created", "status", "risk_level", "created_at")`

### 9. `behavior_logs`
Granular session telemetry and behavioral keystroke / mouse dynamics.
- `id` (UUID, PK)
- `user_id` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `device_id` (UUID, FK -> `devices.id` ON DELETE SET NULL, INDEX)
- `ip_id` (UUID, FK -> `ip_addresses.id` ON DELETE SET NULL, INDEX)
- `session_id` (VARCHAR(64), NOT NULL, INDEX)
- `ip_address` (VARCHAR(45), NULLABLE)
- `device_fingerprint` (VARCHAR(255), NULLABLE)
- `user_agent` (TEXT, NULLABLE)
- `login_hour` (INTEGER, NULLABLE)
- `typing_speed` (FLOAT, NULLABLE)
- `mouse_velocity` (FLOAT, NULLABLE)
- `geo_country` (VARCHAR(60), NULLABLE)
- `geo_city` (VARCHAR(60), NULLABLE)
- `is_vpn` (BOOLEAN, DEFAULT FALSE)
- `is_tor` (BOOLEAN, DEFAULT FALSE)
- `failed_logins` (INTEGER, DEFAULT 0)
- `device_change` (BOOLEAN, DEFAULT FALSE)
- `anomaly_score` (FLOAT, NULLABLE, INDEX)
- `risk_level` (ENUM `risklevel`, NULLABLE, INDEX)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW, INDEX)

### 10. `audit_logs`
System-wide security audit trail.
- `id` (UUID, PK)
- `user_id` (UUID, FK -> `users.id` ON DELETE SET NULL, INDEX)
- `action` (VARCHAR(100), NOT NULL, INDEX)
- `entity_type` (VARCHAR(50), NULLABLE, INDEX)
- `entity_id` (VARCHAR(64), NULLABLE)
- `ip_address` (VARCHAR(45), NULLABLE)
- `details` (JSONB / JSON, NULLABLE)
- `created_at` (TIMESTAMPTZ, DEFAULT NOW, INDEX)

---

## 3. Atomic Multi-Table SQL Transactions

All service layer operations modifying related tables execute within explicit atomic transaction blocks (`try: ... self.db.commit() except: self.db.rollback() raise`):

### Example: Credit Fraud Prediction Pipeline (`FraudDetectionService.predict_credit`)
1. **Resolve Normalization**: Retrieve or create `Merchant`, `Device`, `IPAddress`, and active `ModelMetadata`.
2. **Insert `Transaction`**: Links all 4 resolved foreign keys.
3. **Insert `FraudPrediction`**: Records inference latency, SHAP values, and decision (`ALLOW`, `REVIEW`, `BLOCK`).
4. **Conditionally Insert `FraudAlert`**: If risk is elevated, creates triage alert linked to the transaction and prediction.
5. **Insert `AuditLog`**: Logs the security decision event.
6. **Commit / Rollback**: If any insert fails, `self.db.rollback()` guarantees zero orphaned records.

---

## 4. SQL Join Query Strategies

To eliminate N+1 queries across complex relationships, services use SQLAlchemy 2.0 `joinedload` and SQL `JOIN` clauses:

```python
# app/services/transaction_service.py
q = self.db.query(Transaction).options(
    joinedload(Transaction.merchant_rel),
    joinedload(Transaction.user),
    joinedload(Transaction.device),
    joinedload(Transaction.ip_rel),
    joinedload(Transaction.prediction),
    joinedload(Transaction.alert),
)
```

For search queries spanning multiple tables:
```python
q = (
    q.outerjoin(Transaction.merchant_rel)
    .outerjoin(Transaction.user)
    .filter(
        (Transaction.merchant.ilike(search_pattern))
        | (Merchant.name.ilike(search_pattern))
        | (User.name.ilike(search_pattern))
    )
)
```

---

## 5. Alembic Migrations

Migrations are managed under `backend/alembic/`:

- **Environment Config**: `backend/alembic/env.py` (reads connection URL dynamically from centralized `settings.database_url`).
- **Initial Baseline Migration**: `backend/alembic/versions/0001_initial_neon_schema.py`.

### Running Migrations:
```bash
cd backend
alembic upgrade head
```

### Creating New Revisions:
```bash
alembic revision --autogenerate -m "add_column_name"
```

### Rollback:
```bash
alembic downgrade -1
```

---

## 6. Seeding Data
To populate the database with realistic normalized data for local exploration or staging:
```bash
python -m scripts.seed_data
```
This populates all 10 normalized tables with cross-referenced foreign keys, realistic distributions, SHAP explainability records, and an administrator account (`admin@detexa.io`).
