# Detexa Fraud Decision Engine Specification

## 1. Executive Summary & Design Principles

The **Detexa Fraud Decision Engine** (`app/decision/`) sits downstream of machine learning inference and real-time streaming state. It strictly decouples **statistical probability estimation (ML)** from **business risk policy (Decisions)**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Decision Engine Context                         │
│                                                                        │
│   ┌─────────────────┐ ┌──────────────────┐ ┌───────────────────────┐   │
│   │ ML Fraud Score  │ │ Real-Time Redis  │ │ Neo4j Graph Collusion │   │
│   │ [0.000 - 1.000] │ │ Sliding Windows  │ │  Risk & Shared Nodes  │   │
│   └────────┬────────┘ └────────┬─────────┘ └───────────┬───────────┘   │
└────────────┼───────────────────┼───────────────────────┼───────────────┘
             ▼                   ▼                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FraudDecisionEngine Arbitrator                    │
│                                                                        │
│  - VelocityBurstRule (1m burst >= 5 -> BLOCK, 5m >= 12 -> REVIEW)     │
│  - AuthenticationFailureRule (5m declines >= 3 -> BLOCK, >= 2 -> CHAL) │
│  - AmountSpikeRule (Hard ceiling >= $10k, deviation >= 4.5x -> CHAL)   │
│  - DeviceTrustRule (3+ devices -> BLOCK, new device -> CHALLENGE)      │
│  - IPHoppingRule (3+ IPs -> REVIEW, IP changed -> CHALLENGE)           │
│  - GraphCollusionRule (3+ shared users -> BLOCK, ring risk -> CHAL)    │
│  - DiurnalTimingRule (Off-peak nocturnal hours -> CHALLENGE)           │
│  - MLScoreThresholdRule (ML probability tiering)                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Four-Tier Deterministic Action Output                 │
│                                                                        │
│    [ALLOW]              [CHALLENGE]           [REVIEW]       [BLOCK]   │
│  Clearance             Step-Up 3DS/MFA        Analyst Queue  Decline   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Idempotent PostgreSQL Persistence & Audit Trail           │
│  - `transactions` (risk_level, label, fraud_score)                     │
│  - `fraud_predictions` (decision, input_hash, shap_values)             │
│  - `fraud_alerts` (reason_codes, triggered_rules, status)              │
│  - `audit_logs` (analyst overrides, security audit trail)              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Four-Tier Decision Outcomes

| Decision Action | Action Code | Risk Level | Description & Action |
|---|---|---|---|
| **ALLOW** | `ALLOW` | **Low** | Transaction automatically approved with frictionless checkout. |
| **CHALLENGE** | `CHALLENGE` | **Medium** | Step-up authentication required (e.g. 3D-Secure 2.0, SMS OTP, or biometric push notification). |
| **REVIEW** | `REVIEW` | **Medium / High** | Transaction held in analyst queue for manual inspection prior to settlement. |
| **BLOCK** | `BLOCK` | **High** | Immediate authorization decline due to critical policy violation or high fraud probability. |

---

## 3. Priority Arbitration Hierarchy

Rules are evaluated concurrently against the `DecisionContext`. The arbitrator resolves conflicts using strict severity ordering:

$$\mathbf{BLOCK} \succ \mathbf{REVIEW} \succ \mathbf{CHALLENGE} \succ \mathbf{ALLOW}$$

1. If **any rule** triggers a `BLOCK` $\longrightarrow$ Final decision is **`BLOCK`**.
2. Else if **any rule** triggers a `REVIEW` $\longrightarrow$ Final decision is **`REVIEW`**.
3. Else if **any rule** triggers a `CHALLENGE` $\longrightarrow$ Final decision is **`CHALLENGE`** (`requires_step_up_auth = True`).
4. Otherwise $\longrightarrow$ Final decision is **`ALLOW`**.

---

## 4. Configurable Rules & Parameter Mapping

All rule thresholds and switches are dynamically configured through environment variables:

| Rule ID | Rule Name | Action Triggers | Config Variable | Default |
|---|---|---|---|---|
| `RULE_VELOCITY` | Velocity Burst | $v_{\text{1m}} \ge 5 \to \text{BLOCK}$<br>$v_{\text{5m}} \ge 12 \to \text{REVIEW}$ | `RULE_MAX_VELOCITY_1M`<br>`RULE_MAX_VELOCITY_5M` | `5`<br>`12` |
| `RULE_AUTH_FAIL` | Auth Decline Streak | Declines $\ge 3 \to \text{BLOCK}$<br>Declines $\ge 2 \to \text{CHALLENGE}$ | `RULE_MAX_FAILED_AUTH_5M` | `3` |
| `RULE_AMOUNT` | Spending Deviation | $\text{Amt} \ge \$10,000 \to \text{REVIEW}$<br>$\text{Dev} \ge 4.5\times \to \text{CHALLENGE}$ | `RULE_MAX_AMOUNT_HARD_LIMIT`<br>`RULE_MAX_AMOUNT_DEVIATION` | `10000.0`<br>`4.5` |
| `RULE_DEVICE` | Hardware Hopping | $\ge 3\text{ devices} \to \text{BLOCK}$<br>New device $> \$150 \to \text{CHALLENGE}$ | `RULE_ENABLE_DEVICE_CHANGE_CHALLENGE` | `true` |
| `RULE_IP_HOP` | IP Hopping | $\ge 3\text{ IPs} \to \text{REVIEW}$<br>IP hop $> \$200 \to \text{CHALLENGE}$ | `RULE_ENABLE_IP_HOPPING_CHALLENGE` | `true` |
| `RULE_GRAPH` | Graph Collusion | $\ge 3\text{ shared users} \to \text{BLOCK}$<br>Risk score $\ge 0.65 \to \text{CHALLENGE}$ | `RULE_MAX_GRAPH_SHARED_USERS`<br>`RULE_MAX_GRAPH_RISK_SCORE` | `3`<br>`0.65` |
| `RULE_DIURNAL` | Nocturnal Window | $02:00\text{--}05:00\text{ UTC} > \$500 \to \text{CHALLENGE}$ | `RULE_OFF_PEAK_NIGHT_THRESHOLD` | `500.0` |
| `RULE_ML_SCORE` | Model Score Tiers | $P \ge 0.85 \to \text{BLOCK}$<br>$P \ge 0.65 \to \text{REVIEW}$<br>$P \ge 0.40 \to \text{CHALLENGE}$<br>$P < 0.40 \to \text{ALLOW}$ | `DECISION_THRESHOLD_REVIEW`<br>`DECISION_THRESHOLD_CHALLENGE`<br>`DECISION_THRESHOLD_ALLOW` | `0.85`<br>`0.65`<br>`0.40` |

---

## 5. PostgreSQL Schema Persistence & Audit Trails

Every decision is atomically stored across normalized tables in Neon PostgreSQL via `PostgresDecisionStorage`:

1. **`transactions`**: Updates `risk_level` (`Low`, `Medium`, `High`), `fraud_score`, `is_fraud`, and `label`.
2. **`fraud_predictions`**: Records `decision` (`ALLOW`, `CHALLENGE`, `REVIEW`, `BLOCK`), `input_hash`, `latency_ms`, `shap_values`, and `model_version`.
3. **`fraud_alerts`**: Creates open incident records whenever decision is `BLOCK`, `REVIEW`, or `CHALLENGE`, recording all `reason_codes` and `triggered_rules`.
4. **`audit_logs`**: Logs complete security audit entries (`action: DECISION_ALLOW/BLOCK/REVIEW/CHALLENGE`).

---

## 6. REST API Endpoints

Mounted under `/api/v1/decisions`:
- `GET /api/v1/decisions`: List filtered, paginated decision logs.
- `GET /api/v1/decisions/{decision_id}`: Retrieve single decision details with linked relational transaction.
- `GET /api/v1/decisions/stats`: Aggregate counts and percentage breakdowns across `ALLOW`, `CHALLENGE`, `REVIEW`, `BLOCK`.
- `GET /api/v1/decisions/rules/policy`: Retrieve active rules and threshold configuration.
- `POST /api/v1/decisions/evaluate/context`: Simulate/evaluate arbitrary context through the complete decision engine.
- `POST /api/v1/decisions/{decision_id}/override`: Analyst/Admin manual override with mandatory audit justification.
