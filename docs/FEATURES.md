# Detexa Unified Fraud Feature Building Layer

## 1. Executive Summary & Architecture

The **Detexa Unified Fraud Feature Building Layer** (`app/features/`) provides a single, deterministic source of truth for feature engineering across the entire fraud detection lifecycle.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Data & Streaming Sources                        │
│                                                                        │
│   ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  ┌─────────┐   │
│   │ Raw / History │  │  Biometrics   │  │ Redis Store │  │  Neo4j  │   │
│   │  Transaction  │  │ & Behavioral  │  │ Real-Time   │  │  Graph  │   │
│   │  (PCA + Amt)  │  │ (Typing/VPN)  │  │  (Windows)  │  │ (Links) │   │
│   └───────┬───────┘  └───────┬───────┘  └──────┬──────┘  └────┬────┘   │
└───────────┼──────────────────┼─────────────────┼──────────────┼────────┘
            ▼                  ▼                 ▼              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   UnifiedFraudFeatureBuilder (v3.0.0)                  │
│                                                                        │
│  - Deterministic transformations & cyclical time encodings             │
│  - Non-linear PCA interaction terms (V14*V12, V14*V17, etc.)          │
│  - Canonical ordering: exactly 61 features                             │
│  - Automated default imputation & missing-value safety                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│ Model Train  │             │ Batch Offline│             │  Real-Time   │
│  (XGBoost)   │             │  Inference   │             │ Online & Str │
└──────────────┘             └──────────────┘             └──────────────┘
```

---

## 2. Preventing Training-Serving Skew

A primary failure mode in machine learning systems is **training-serving skew**—where features during online inference differ from training in calculation logic, data types, column order, or missing value imputations.

Detexa eliminates training-serving skew through:
1. **Single Engine**: [`UnifiedFraudFeatureBuilder`](file:///c:/Users/13ver/Desktop/New/folder/project/Detexa/backend/app/features/builder.py) transforms raw data for both training (`build_training_dataframe`) and real-time inference (`build_realtime_vector`).
2. **Canonical Schema Ordering**: Strict column ordering guaranteed via `CANONICAL_FEATURE_NAMES` (61 features).
3. **Deterministic Imputation**: `FEATURE_DEFAULT_MAP` ensures zero NaN/null values reach the XGBoost / ML estimators.
4. **Schema Versioning**: Every vector is tagged with `FEATURE_SCHEMA_VERSION = "3.0.0"`.

---

## 3. Canonical Feature Dictionary (Schema v3.0.0)

### Group 1: Transaction & PCA Components (37 Features)

| Feature Name | Type | Default | Description / Formula |
|---|---|---|---|
| `amount` | `float` | `0.0` | Transaction value in base currency ($) |
| `log_amount` | `float` | `0.0` | $\ln(1 + \max(\text{amount}, 0))$ |
| `amount_sq` | `float` | `0.0` | $\text{amount}^2$ |
| `v_norm` | `float` | `0.0` | $\sqrt{\sum_{i=1}^{28} V_i^2}$ (L2 magnitude of PCA vector) |
| `v1` $\dots$ `v28` | `float` | `0.0` | Principal component dimensions $V_1 \dots V_{28}$ |
| `v1_v2_interaction` | `float` | `0.0` | $V_1 \times V_2$ |
| `v3_v7_interaction` | `float` | `0.0` | $V_3 \times V_7$ |
| `v4_v11_interaction` | `float` | `0.0` | $V_4 \times V_{11}$ |
| `v12_v10_interaction`| `float` | `0.0` | $V_{12} \times V_{10}$ |
| `v14_v12_interaction`| `float` | `0.0` | $V_{14} \times V_{12}$ (*Top predictive driver: 49.2% gain*) |
| `v14_v17_interaction`| `float` | `0.0` | $V_{14} \times V_{17}$ |
| `v17_v12_interaction`| `float` | `0.0` | $V_{17} \times V_{12}$ |

---

### Group 2: Temporal & Diurnal Features (4 Features)

| Feature Name | Type | Default | Description / Formula |
|---|---|---|---|
| `hour_of_day` | `float` | `12.0` | Continuous transaction hour in UTC $[0.0, 23.99]$ |
| `sin_time` | `float` | `0.0` | $\sin\left(\frac{2\pi \cdot \text{hour}}{24}\right)$ |
| `cos_time` | `float` | `1.0` | $\cos\left(\frac{2\pi \cdot \text{hour}}{24}\right)$ |
| `is_night_txn` | `float` | `0.0` | Binary flag ($1.0$ if $\text{hour} < 06:00$ or $\ge 22:00$, else $0.0$) |

---

### Group 3: Behavioral & Biometrics (7 Features)

| Feature Name | Type | Default | Description / Formula |
|---|---|---|---|
| `typing_speed` | `float` | `45.0` | Keystroke dynamics speed (characters/sec) |
| `mouse_velocity` | `float` | `250.0` | Cursor pointer velocity (px/sec) |
| `failed_logins` | `float` | `0.0` | Recent authentication failures |
| `is_vpn` | `float` | `0.0` | Anonymizing VPN connection ($1.0$ or $0.0$) |
| `is_tor` | `float` | `0.0` | Tor exit node connection ($1.0$ or $0.0$) |
| `device_change` | `float` | `0.0` | Rapid hardware switch indicator ($1.0$ or $0.0$) |
| `risk_combo` | `float` | `0.0` | $\text{is\_vpn} + 2\cdot\text{is\_tor} + \text{device\_change}$ |

---

### Group 4: Redis Real-Time Sliding Windows (15 Features)

| Feature Name | Type | Default | Description / Formula |
|---|---|---|---|
| `velocity_1m` | `float` | `1.0` | Transaction count in last 60 seconds |
| `velocity_5m` | `float` | `1.0` | Transaction count in last 5 minutes |
| `velocity_15m` | `float` | `1.0` | Transaction count in last 15 minutes |
| `velocity_1h` | `float` | `1.0` | Transaction count in last 1 hour |
| `velocity_24h` | `float` | `1.0` | Cumulative transaction count in last 24 hours |
| `rolling_amount_1h` | `float` | `0.0` | Sum of transaction amounts in 1 hour |
| `avg_amount_1h` | `float` | `0.0` | Mean transaction amount in 1 hour |
| `max_amount_1h` | `float` | `0.0` | Maximum transaction amount in 1 hour |
| `rolling_amount_24h`| `float` | `0.0` | Sum of transaction amounts in 24 hours |
| `avg_amount_24h` | `float` | `0.0` | Mean transaction amount in 24 hours |
| `amount_deviation_ratio` | `float` | `1.0` | $\frac{\text{amount}}{\max(\mu_{\text{1h}}, 10.0)}$ |
| `distinct_merchants_1h` | `float` | `1.0` | Unique merchants transacted with in 1 hour |
| `distinct_categories_1h`| `float` | `1.0` | Unique merchant categories visited in 1 hour |
| `distinct_devices_15m` | `float` | `1.0` | Unique device fingerprints in 15 minutes |
| `distinct_ips_15m` | `float` | `1.0` | Unique IP addresses routed through in 15 minutes |
| `is_foreign_transaction` | `float` | `0.0` | Binary indicator of cross-border card use |
| `failed_auth_5m` | `float` | `0.0` | Card declines in last 5 minutes |
| `failed_auth_1h` | `float` | `0.0` | Card declines in last 1 hour |
| `consecutive_failures` | `float` | `0.0` | Consecutive decline streak |
| `high_risk_flags_24h` | `float` | `0.0` | High-risk alerts triggered by user in 24 hours |

---

### Group 5: Neo4j Graph Relationship Features (8 Features)

| Feature Name | Type | Default | Description / Formula |
|---|---|---|---|
| `graph_shared_device_users` | `float` | `1.0` | Distinct users sharing the current hardware device |
| `graph_shared_ip_users` | `float` | `1.0` | Distinct users sharing the current IP address |
| `graph_shared_device_frauds`| `float` | `0.0` | Prior confirmed fraud transactions on this device |
| `graph_shared_ip_frauds` | `float` | `0.0` | Prior confirmed fraud transactions on this IP |
| `graph_fraud_ring_size` | `float` | `1.0` | Connected entity count in 2-hop neighborhood |
| `graph_is_device_shared` | `float` | `0.0` | Binary flag (`graph_shared_device_users > 1`) |
| `graph_is_ip_shared` | `float` | `0.0` | Binary flag (`graph_shared_ip_users > 1`) |
| `graph_risk_score` | `float` | `0.0` | Calibrated link analysis score $[0.0, 1.0]$ |

---

## 4. Usage & Integration Examples

### Python Unified Feature Extraction
```python
from app.features import UnifiedFraudFeatureBuilder
from app.feature_store import get_feature_store
from app.graph import get_graph_service

# 1. Fetch real-time Redis and Neo4j states
user_key = "usr_998124"
redis_features = get_feature_store().get_hot_features(
    user_key=user_key,
    current_amount=249.99,
    current_merchant="Amazon",
    current_device="fp_abc123",
    current_ip="192.168.1.1",
)
graph_features = get_graph_service().get_features(
    user_id=user_key,
    current_device_fp="fp_abc123",
    current_ip="192.168.1.1",
)

# 2. Build canonical unified vector
vector = UnifiedFraudFeatureBuilder.build_realtime_vector(
    payload={
        "user_id": user_key,
        "amount": 249.99,
        "v1": -1.35, "v2": 0.88, ..., "v28": 0.05,
    },
    redis_features=redis_features,
    graph_features=graph_features,
)

# 3. Export for ML models
df_for_model = vector.to_dataframe()  # Exactly 61 canonical columns
numpy_array = vector.to_numpy()      # Shape (61,) float32
```

---

## 5. REST API Endpoints

- **`GET /api/v1/features/schema/metadata`**: Returns canonical schema metadata, version (`3.0.0`), group counts, and feature definitions.
- **`GET /api/v1/features/vector/{user_key}`**: Constructs and serves the complete 61-feature vector for a given user or transaction context.
