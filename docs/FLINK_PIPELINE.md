# Detexa Apache Flink Real-Time Stream Processing Pipeline

## 1. Executive Summary & Architectural Overview

The **Detexa Flink Streaming Layer** provides low-latency, stateful event processing for real-time credit card fraud detection. It continuously consumes transaction events from Apache Kafka, computes multi-scale temporal and behavioral sliding-window features, runs real-time XGBoost ML scoring and multi-tier rule decisioning, and idempotently sinks results to Neon PostgreSQL and egress Kafka topics.

```
┌────────────────────────┐
│  FastAPI REST / Ingest │
└───────────┬────────────┘
            │  Kafka Producer (detexa.transactions.raw)
            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Apache Flink Streaming Subsystem                     │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ Kafka Source Operator (detexa.transactions.raw)                │   │
│   │ + Watermarking (BoundedOutOfOrderness: 5000ms)                 │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │ keyBy(user_id / partition_key)     │
│                                   ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ Stateful Feature Enrichment Operator                           │   │
│   │  - Multi-scale velocity (1m, 5m, 15m, 1h, 24h)                 │   │
│   │  - Rolling monetary statistics (sum, mean, max, deviation)     │   │
│   │  - Behavioral tracking (failed bursts, device/IP hopping)      │   │
│   │  - Diurnal cyclical timing (sin/cos hour, off-peak flags)      │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │ FlinkEnrichedEvent                 │
│                                   ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ Real-Time ML Fraud Scoring Operator (XGBoost Pipeline v2.0.0)  │   │
│   │  - 43 PCA + Engineered Features -> P(Fraud) + SHAP Drivers     │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │ Score + Enriched Features          │
│                                   ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ Multi-Tier Decision Operator                                   │   │
│   │  - Velocity Burst / Auth Failures / Risk Threshold Evaluation  │   │
│   │  - Decisions: ALLOW | REVIEW | BLOCK                           │   │
│   └───────────────┬────────────────────────────────┬───────────────┘   │
└───────────────────┼────────────────────────────────┼───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐  ┌───────────────────────────────┐
│ Idempotent PostgreSQL Sink           │  │ Kafka Egress Sink             │
│  - transactions, fraud_predictions   │  │  - detexa.transactions.scored │
│  - fraud_alerts, devices, ip_addrs   │  │  - detexa.alerts.high_risk    │
│  - audit_logs (Atomic SQL Txn)       │  └───────────────────────────────┘
└──────────────────────────────────────┘
```

---

## 2. Decoupling & Module Separation

The Flink streaming system is located entirely under `backend/flink/`, maintaining strict decoupling from the FastAPI web application:

| Directory / File | Description |
|---|---|
| `backend/flink/config.py` | Centralized Flink streaming configuration loaded from environment variables |
| `backend/flink/models/state_schemas.py` | Data contracts for window metrics, user state, and enriched stream events |
| `backend/flink/windows/velocity_window.py` | Multi-scale sliding window transaction velocity counter |
| `backend/flink/windows/monetary_window.py` | Rolling monetary sum, moving average, and deviation ratio calculators |
| `backend/flink/windows/behavioral_window.py` | Failed transaction tracking, device/IP hopping, and cyclical timing |
| `backend/flink/operators/feature_enrichment_operator.py` | Stateful keyed stream operator maintaining bounded state per user |
| `backend/flink/operators/fraud_scoring_operator.py` | Real-time XGBoost model inference operator with SHAP importance |
| `backend/flink/operators/decision_operator.py` | Multi-tier policy engine evaluating rules + ML scores into decisions |
| `backend/flink/operators/postgres_sink.py` | Thread-safe idempotent PostgreSQL writer with multi-table transactions |
| `backend/flink/operators/kafka_sink.py` | Outbound event publisher for scored transactions and high-risk alerts |
| `backend/flink/job.py` | PyFlink DAG builder and streaming coordinator |
| `backend/flink/run_job.py` | Standalone CLI streaming runner script |

---

## 3. Streaming Feature Engineering

### 3.1 Multi-Scale Transaction Velocity
Velocity features capture rapid transaction bursts across 5 temporal scales:
- **`velocity_1m`**: Transaction frequency in the last 60 seconds (critical for brute-force/card-testing attacks).
- **`velocity_5m`**: Frequency over 5 minutes.
- **`velocity_15m`**: Frequency over 15 minutes.
- **`velocity_1h`**: Frequency over 1 hour.
- **`velocity_24h`**: Frequency over 24 hours.

### 3.2 Monetary & Deviation Windows
- **`rolling_amount_1h`**: Sum of transaction amounts in the last 1 hour.
- **`avg_amount_1h`**: Rolling mean transaction value over 1 hour.
- **`max_amount_1h`**: Maximum single transaction value in 1 hour.
- **`rolling_amount_24h`**: 24-hour cumulative spending.
- **`avg_amount_24h`**: 24-hour mean transaction value.
- **`amount_deviation_ratio`**: Current transaction amount divided by user's 1h/24h rolling average:
  $$\text{Deviation Ratio} = \frac{\text{Amount}}{\max(\mu_{\text{1h}}, 10.0)}$$

### 3.3 Behavioral & Hardware Identity
- **`failed_txn_count_5m`**: Consecutive authentication/authorization failures in 5 minutes.
- **`failed_txn_count_1h`**: Total failed transactions in 1 hour.
- **`distinct_devices_15m`**: Count of unique device fingerprints observed in 15 minutes.
- **`device_changed`**: Boolean flag indicating if current device differs from the previous transaction.
- **`distinct_ips_15m`**: Count of unique IP addresses observed in 15 minutes (IP hopping indicator).
- **`ip_changed`**: Boolean flag indicating rapid IP switching.
- **`distinct_merchants_1h`**: Number of distinct merchants transacted with in 1 hour.

### 3.4 Temporal & Diurnal Features
- **`hour_of_day`**: Hour in UTC ($0.0 \dots 23.99$).
- **`is_unusual_hour`**: Boolean flag indicating transactions occurring during off-peak diurnal hours ($02:00\text{--}05:00\text{ UTC}$).
- **`sin_hour` & `cos_hour`**: Cyclical continuous encodings:
  $$\sin\left(\frac{2\pi \cdot \text{hour}}{24}\right), \quad \cos\left(\frac{2\pi \cdot \text{hour}}{24}\right)$$
- **`seconds_since_last_txn`**: Delta time between consecutive transactions.

---

## 4. State Management & Fault Tolerance

- **Keyed State**: State is partitioned by `user_id` (or `partition_key` / `transaction_ref`), ensuring linear scalability across parallel task slots.
- **Bounded State Retention**: In-memory state structures maintain bounded historical windows (last 24 hours or max 200 events per key) to prevent memory leaks and out-of-memory errors.
- **Watermarking Strategy**: Bounded-out-of-orderness watermarks (default $5000\text{ms}$) allow the pipeline to correctly handle delayed and out-of-order network packets.
- **Checkpoints**: Configured for `EXACTLY_ONCE` state snapshotting at $5000\text{ms}$ intervals with a minimum pause of $2000\text{ms}$ between checkpoints.

---

## 5. Machine Learning Scoring & Decision Logic

### 5.1 Real-Time Model Inference
The `FraudScoringOperator` loads the trained XGBoost pipeline (`backend/app/ml/saved/credit_fraud_pipeline.pkl`).
It feeds 28 PCA features, the transaction amount, cyclical time features, and rolling window interactions into the classifier, yielding:
- **`fraud_score`**: Calibrated probability in range $[0.0, 1.0]$.
- **`shap_drivers`**: Top feature contributions explaining the model's score.

### 5.2 Multi-Tier Decision Matrix

| Trigger / Condition | Decision | Risk Level | Reason Code |
|---|---|---|---|
| `velocity_1m >= 5` | **BLOCK** | High | `RULE_BURST_VELOCITY_1M_EXCEEDED` |
| `failed_txn_count_5m >= 3` | **BLOCK** | High | `RULE_CONSECUTIVE_AUTH_FAILURES_N` |
| `distinct_devices_15m >= 3` | **BLOCK** | High | `RULE_RAPID_DEVICE_HOPPING_N` |
| `ml_fraud_score >= 0.85` | **BLOCK** | High | `ML_HIGH_RISK_SCORE_X` |
| `velocity_5m >= 12` | **REVIEW** | Medium | `RULE_ELEVATED_VELOCITY_5M` |
| `failed_txn_count_1h >= 5` | **REVIEW** | Medium | `RULE_EXCESSIVE_DECLINES_1H` |
| `is_unusual_hour` and `amount > $500` | **REVIEW** | Medium | `RULE_UNUSUAL_TIMING_OFF_PEAK` |
| `device_changed` and `velocity_5m >= 2` | **REVIEW** | Medium | `RULE_NEW_DEVICE_VELOCITY_BURST` |
| `distinct_ips_15m >= 3` | **REVIEW** | Medium | `RULE_RAPID_IP_HOPPING` |
| `amount_deviation_ratio > 4.5` and `amount > $800` | **REVIEW** | Medium | `RULE_AMOUNT_DEVIATION_SPIKE` |
| `ml_fraud_score >= 0.50` | **REVIEW** | Medium | `ML_ELEVATED_RISK_SCORE_X` |
| *Otherwise* | **ALLOW** | Low | `ML_LOW_RISK_NORMAL` |

---

## 6. Sinks & Idempotency Guarantees

### 6.1 PostgreSQL Idempotent Sink
The `PostgreSQLSinkOperator` executes within an atomic SQL transaction:
1. Performs a pre-insert check on `Transaction.transaction_ref` to eliminate duplicate processing.
2. Resolves or creates related entities (`merchants`, `devices`, `ip_addresses`).
3. Inserts normalized record into `transactions` with PCA features $V_1 \dots V_{28}$.
4. Inserts inference audit record into `fraud_predictions`.
5. Creates open `fraud_alerts` record for any transaction with `REVIEW` or `BLOCK` decisions.
6. Records an entry in `audit_logs` for compliance.

### 6.2 Kafka Egress Sink
1. **`detexa.transactions.scored`**: Emits full transaction payload enriched with window metrics, fraud score, risk level, decision, and SHAP top features.
2. **`detexa.alerts.high_risk`**: Emits dedicated alert events whenever a transaction is flagged for `REVIEW` or `BLOCK`.

---

## 7. Configuration & Execution Guide

### 7.1 Environment Variables
All streaming parameters are configurable via `backend/.env`:

```env
# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TRANSACTIONS_TOPIC=detexa.transactions.raw
KAFKA_TRANSACTIONS_SCORED_TOPIC=detexa.transactions.scored
KAFKA_ALERTS_TOPIC=detexa.alerts.high_risk
FLINK_CONSUMER_GROUP=detexa-flink-stream-group

# Flink Engine Settings
FLINK_PARALLELISM=2
FLINK_CHECKPOINT_INTERVAL_MS=5000
FLINK_WATERMARK_MAX_OUT_OF_ORDERNESS_MS=5000

# Scoring Thresholds
FRAUD_THRESHOLD=0.50
HIGH_RISK_THRESHOLD=0.85
```

### 7.2 Running the Flink Streaming Worker
To start the continuous Flink streaming worker:

```bash
# From backend root
cd backend
python -m flink.run_job
```
