# Detexa Real-Time Transaction Streaming Architecture

## 1. Architecture Overview & Event Flow

Detexa implements an enterprise-grade, low-latency stream processing pipeline designed to score transactions in under **50 milliseconds**. The pipeline is decoupled through an event-driven architecture using **Apache Kafka** for distributed streaming, **Apache Flink** for stateful sliding-window feature aggregation, **XGBoost** for machine learning inference, a multi-tier **Decision Engine**, and **Neon PostgreSQL** for normalized persistence.

```
                    ┌─────────────────────────────────────────────────────────┐
                    │               Client / Payment Gateway                  │
                    └────────────────────────────┬────────────────────────────┘
                                                 │ HTTP POST /api/v1/streaming/transactions
                                                 │ (Idempotency-Key: <UUID>)
                    ┌────────────────────────────▼────────────────────────────┐
                    │          Transaction REST Ingestion API                 │
                    │      (Validation & Idempotency Header Stamping)         │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
                                     [Kafka Producer: Snappy + acks=all]
                                                 │
                    ┌────────────────────────────▼────────────────────────────┐
                    │      Kafka Topic: detexa.transactions.raw               │
                    │      (Partitioned by user_id / card_key)                │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
                                     [Flink Stream Consumer]
                                                 │
                    ┌────────────────────────────▼────────────────────────────┐
                    │           Flink Stateful Stream Processor               │
                    │   ┌─────────────────────────────────────────────────┐   │
                    │   │ 1. Sliding Window State (1m, 5m, 1h)            │   │
                    │   │    - Velocity counts, rolling sum, avg amount   │   │
                    │   │    - Cross-border mismatch, device consistency  │   │
                    │   ├─────────────────────────────────────────────────┤   │
                    │   │ 2. Real-Time Feature Processing                 │   │
                    │   │    - Diurnal time sin/cos, log1p(Amount)        │   │
                    │   │    - PCA interaction terms (V14*V12, V12*V10)   │   │
                    │   ├─────────────────────────────────────────────────┤   │
                    │   │ 3. ML Fraud Inference (XGBoost v2.0.0 Pipeline) │   │
                    │   │    - Probability scoring + SHAP feature drivers │   │
                    │   ├─────────────────────────────────────────────────┤   │
                    │   │ 4. Multi-Tier Decision Engine                   │   │
                    │   │    - Hard rules + ML score -> ALLOW/REVIEW/BLOCK│   │
                    │   └─────────────────────────────────────────────────┘   │
                    └──────────────┬───────────────────────────┬──────────────┘
                                   │                           │
                   [Atomic SQL Transaction]         [Kafka Outbound Egress]
                                   │                           │
                    ┌──────────────▼──────────────┐ ┌──────────▼──────────────┐
                    │       Neon PostgreSQL       │ │      Apache Kafka       │
                    │  - transactions             │ │  detexa.transactions.  │
                    │  - fraud_predictions        │ │    scored               │
                    │  - fraud_alerts             │ │  detexa.alerts.         │
                    │  - audit_logs               │ │    high_risk            │
                    └─────────────────────────────┘ └─────────────────────────┘
```

---

## 2. Reusable Event Schemas & Message Envelopes

All events conform to standardized Pydantic v2 schemas in [`app/streaming/event_schemas.py`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/streaming/event_schemas.py):

### 2.1 Standard Event Header (`EventHeader`)
Every event carries metadata guaranteeing end-to-end trace context and idempotency:
- `event_id` (UUID): Unique identifier per message instance.
- `idempotency_key` (String / UUID): Deterministic client or gateway idempotency key.
- `event_type`: Categorical event topic (`TRANSACTION_INGESTED`, `TRANSACTION_SCORED`, `ALERT_GENERATED`, `DECISION_COMMITTED`, `DEAD_LETTER`).
- `timestamp`: ISO-8601 UTC timestamp.
- `source`: Originating service identifier (`detexa-transaction-api`, `detexa-flink-stream-processor`).
- `partition_key`: Explicit key used for Kafka partition routing (e.g. `user_id` or `card_hash`).

### 2.2 Ingestion Event (`TransactionIngestionEvent`)
Published by the Transaction Ingestion API to `detexa.transactions.raw`:
```json
{
  "header": {
    "event_id": "b8f5d023-5e92-4f32-8438-e6b8a8b19330",
    "idempotency_key": "IDEMP-TXN-948201",
    "event_type": "TRANSACTION_INGESTED",
    "timestamp": "2026-10-06T17:30:00.000000Z",
    "source": "detexa-transaction-api",
    "partition_key": "USR-40192"
  },
  "payload": {
    "transaction_ref": "TXN-9F81A02E",
    "amount": 1450.00,
    "currency": "USD",
    "merchant": "CryptoExchangeX",
    "category": "financial_crypto",
    "country": "US",
    "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "device_fingerprint": "fp_chrome_win11_8a92f",
    "ip_address": "198.51.100.42",
    "v1": -1.3598, "v2": -0.07278, "v3": 2.5363, "v4": 1.3781,
    "...": "...",
    "v28": -0.0210
  }
}
```

### 2.3 Scored Transaction Event (`ScoredTransactionEvent`)
Emitted by Flink to `detexa.transactions.scored` containing real-time sliding window telemetry and ML decisions:
```json
{
  "header": { ... },
  "payload": { ... },
  "streaming_features": {
    "velocity_1m": 4,
    "velocity_5m": 7,
    "velocity_1h": 12,
    "rolling_amount_1h": 3850.00,
    "avg_amount_1h": 320.83,
    "amount_deviation_ratio": 4.52,
    "distinct_merchants_1h": 3,
    "is_foreign_transaction": false,
    "is_new_device": false
  },
  "fraud_score": 0.8421,
  "risk_level": "High",
  "decision": "BLOCK",
  "reason_codes": [
    "ML_HIGH_FRAUD_PROBABILITY_0.84",
    "RULE_AMOUNT_DEVIATION_SPIKE"
  ],
  "shap_top_features": [
    {"feature": "V14_V12_interaction", "shap_value": 0.4924},
    {"feature": "V14", "shap_value": 0.1316}
  ],
  "latency_ms": 32.4,
  "model_version": "2.0.0"
}
```

---

## 3. Kafka Ingestion & Key Partitioning

### 3.1 Broker Topology & Topic Specifications
- **`detexa.transactions.raw`**: 12 Partitions, Replication Factor 3, Retention 7 days.
- **`detexa.transactions.scored`**: 12 Partitions, Replication Factor 3, Retention 14 days.
- **`detexa.alerts.high_risk`**: 6 Partitions, Replication Factor 3, Retention 30 days.
- **`detexa.dlq`**: Dead Letter Queue for poisoned payloads.

### 3.2 Key-Based Partitioning
- Messages are partitioned strictly by `partition_key = user_id` (or `card_id` / `transaction_ref`).
- **Guarantee**: All transactions for a specific user/card arrive in strict monotonic chronological order within the same Kafka partition, preventing race conditions during sliding window calculation.

### 3.3 Producer Reliability Settings:
- `enable.idempotence = true` (Prevents duplicate broker-side messages during network retries)
- `acks = "all"` (Guarantees persistence to in-sync replicas)
- `retries = 5`
- `max.in.flight.requests.per.connection = 1`

---

## 4. Flink Real-Time Feature Processing

The Flink stream processing layer computes stateful window metrics:

| Window Scope | Metric | Formula / Detection Target |
|---|---|---|
| **1-Minute Tumbling** | `velocity_1m` | Card cracking / automated bot bursts ($\ge 5 \rightarrow \text{BLOCK}$) |
| **5-Minute Sliding** | `velocity_5m` | Rapid merchant hopping / card testing ($\ge 12 \rightarrow \text{REVIEW}$) |
| **1-Hour Sliding** | `rolling_amount_1h` | Cumulative spending capacity drain |
| **1-Hour Sliding** | `amount_deviation_ratio` | $\text{Amount} / \text{MovingAverage}_{1h}$ (Anomalous single-purchase spike) |
| **State History** | `is_foreign_transaction` | Rapid geographical relocation without realistic flight time |
| **State History** | `is_new_device` | Unrecognized browser/device fingerprint |

---

## 5. Decision Engine Rule Matrix

The multi-tier Decision Engine evaluates policy rules in a deterministic hierarchy:

```
                  ┌─────────────────────────────────────────┐
                  │        Incoming Scored Event            │
                  └────────────────────┬────────────────────┘
                                       │
                    [Tier 1: Hard Deterministic Policies]
                    - Velocity 1m >= 5 ? ───────────────────────► BLOCK
                    - TOR Network & Amount > $200 ? ────────────► BLOCK
                    - Cross-border & Amount > $1,500 ? ─────────► REVIEW
                    - Amount Deviation > 4.5x ? ────────────────► REVIEW
                    - Micro-Charge Test (Amount < $1.50) ? ─────► REVIEW
                                       │
                                   [No Match]
                                       │
                    [Tier 2: ML Probability Evaluation]
                    - XGBoost Score >= 0.75 ? ──────────────────► BLOCK
                    - 0.40 <= XGBoost Score < 0.75 ? ───────────► REVIEW
                    - XGBoost Score < 0.40 ? ───────────────────► ALLOW
```

---

## 6. Strict Idempotency & Database Integrity

1. **Deterministic Check**: Before persisting, the stream processor verifies if `transaction_ref` or `idempotency_key` already exists in PostgreSQL:
   ```python
   existing_txn = db.query(Transaction).filter(Transaction.transaction_ref == payload.transaction_ref).first()
   if existing_txn:
       logger.info("Idempotent skip: Transaction already committed.")
       return
   ```
2. **Atomic SQL Multi-Table Unit of Work**:
   Within a single SQL transaction block (`db.commit()` / `db.rollback()`):
   - Normalizes & links `Merchant`, `Device`, and `IPAddress` records.
   - Inserts `Transaction` with PCA features ($V_1..V_{28}$) and streaming metadata.
   - Inserts `FraudPrediction` with ML probability, SHAP values, and decision (`ALLOW`, `REVIEW`, `BLOCK`).
   - Inserts `FraudAlert` if decision is not `ALLOW`.
   - Inserts `AuditLog` logging the stream evaluation event.

---

## 7. Redis & Kafka Demarcation

- **Kafka**: Dedicated exclusively as the **event bus and streaming engine** for high-throughput messaging, partition ordering, and stream processing.
- **Redis**: Dedicated exclusively as an **in-memory cache** for dashboard statistics and prediction deduplication.
- **Strict Constraint Adherence**: Redis is **never** used as a message broker (no Redis Pub/Sub or Redis Streams for core pipeline events).
