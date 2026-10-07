# Detexa Neo4j Graph Relationship & Fraud Ring Analysis

## 1. Executive Summary & Graph Data Model

Detexa incorporates **Neo4j Graph Database** to perform real-time entity resolution, identity link analysis, and multi-account collusion detection. While relational databases (PostgreSQL) excel at transactional consistency and Redis serves real-time sliding windows, Neo4j analyzes deep interconnected graph topology to uncover coordinated fraud rings, shared hardware devices, and IP hopping networks.

```
                  ┌──────────────┐
                  │    :User     │
                  └──────┬───────┘
                         │
     ┌───────────────────┼────────────────────┐
     │ [:USES_DEVICE]    │ [:USES_IP]         │ [:PERFORMED]
     ▼                   ▼                    ▼
┌──────────┐       ┌───────────┐       ┌──────────────┐
│ :Device  │       │:IPAddress │       │ :Transaction │
└──────────┘       └───────────┘       └──────┬───────┘
     ▲                   ▲                    │ [:TRANSACTED_AT]
     │                   │                    ▼
     │ [:ORIGINATED]     │ [:ORIGINATED] ┌──────────┐
     └───────────────────┴───────────────┤:Merchant │
                                         └──────────┘
```

---

## 2. Graph Node Labels & Relationship Schemas

### 2.1 Node Entities

| Node Label | Key Identifiers | Indexed Properties | Purpose |
|---|---|---|---|
| `:User` | `id` (UUID / Account ID) | `risk_score`, `created_at`, `last_seen` | Represents customer or cardholder identity |
| `:Device` | `fingerprint` (Browser/Hardware hash) | `is_trusted`, `first_seen`, `last_seen` | Physical device or mobile hardware instance |
| `:IPAddress` | `address` (IPv4 / IPv6) | `country`, `is_vpn`, `is_tor` | Network routing and geolocation endpoint |
| `:Merchant` | `name` | `category`, `risk_score` | Retailer or payment destination |
| `:Transaction` | `ref` (`TXN-...`) | `amount`, `fraud_score`, `is_fraud`, `timestamp` | Financial authorization event |

---

### 2.2 Relationship Types & Semantics

| Relationship Pattern | Cardinality | Edge Properties | Fraud Detection Signal |
|---|---|---|---|
| `(:User)-[:USES_DEVICE]->(:Device)` | $M:N$ | `first_used`, `last_used`, `count` | Device shared across multiple distinct user accounts |
| `(:User)-[:USES_IP]->(:IPAddress)` | $M:N$ | `first_used`, `last_used`, `count` | Distributed proxy abuse / IP hopping networks |
| `(:User)-[:PERFORMED]->(:Transaction)` | $1:N$ | `timestamp`, `amount` | Transaction ownership & velocity history |
| `(:Transaction)-[:TRANSACTED_AT]->(:Merchant)` | $N:1$ | None | Merchant card testing / target cluster |
| `(:Transaction)-[:ORIGINATED_FROM_DEVICE]->(:Device)` | $N:1$ | None | Device fraud origin link |
| `(:Transaction)-[:ORIGINATED_FROM_IP]->(:IPAddress)` | $N:1$ | None | IP fraud origin link |
| `(:User)-[:TRANSACTED_WITH]->(:Merchant)` | $M:N$ | `count`, `total_amount`, `first_transacted` | User-merchant affinity and sudden category deviation |

---

## 3. Cypher Graph Traversal Queries

### 3.1 Synchronizing Transactions into Neo4j
```cypher
MERGE (u:User {id: $user_id})
  ON CREATE SET u.created_at = $ts, u.risk_score = $fraud_score
  ON MATCH SET u.last_seen = $ts

MERGE (m:Merchant {name: $merchant_name})
  ON CREATE SET m.category = $merchant_category

MERGE (u)-[um:TRANSACTED_WITH]->(m)
  ON CREATE SET um.first_transacted = $ts, um.count = 1, um.total_amount = $amount
  ON MATCH SET um.last_transacted = $ts, um.count = um.count + 1, um.total_amount = um.total_amount + $amount

MERGE (t:Transaction {ref: $txn_ref})
  SET t.amount = $amount,
      t.currency = $currency,
      t.fraud_score = $fraud_score,
      t.risk_level = $risk_level,
      t.decision = $decision,
      t.is_fraud = $is_fraud,
      t.timestamp = $ts,
      t.country = $country

MERGE (u)-[:PERFORMED]->(t)
MERGE (t)-[:TRANSACTED_AT]->(m)

FOREACH (_ IN CASE WHEN $device_fp IS NOT NULL THEN [1] ELSE [] END |
    MERGE (d:Device {fingerprint: $device_fp})
      ON CREATE SET d.first_seen = $ts, d.is_trusted = true
      ON MATCH SET d.last_seen = $ts
    MERGE (u)-[ud:USES_DEVICE]->(d)
      ON CREATE SET ud.first_used = $ts, ud.count = 1
      ON MATCH SET ud.last_used = $ts, ud.count = ud.count + 1
    MERGE (t)-[:ORIGINATED_FROM_DEVICE]->(d)
)

FOREACH (_ IN CASE WHEN $ip_addr IS NOT NULL THEN [1] ELSE [] END |
    MERGE (ip:IPAddress {address: $ip_addr})
      ON CREATE SET ip.country = $country, ip.first_seen = $ts
      ON MATCH SET ip.last_seen = $ts
    MERGE (u)-[ui:USES_IP]->(ip)
      ON CREATE SET ui.first_used = $ts, ui.count = 1
      ON MATCH SET ui.last_used = $ts, ui.count = ui.count + 1
    MERGE (t)-[:ORIGINATED_FROM_IP]->(ip)
)
```

---

### 3.2 Extracting Shared-Device & Shared-IP Risk
```cypher
MATCH (u:User {id: $user_id})

// 1. Device sharing & fraud count
OPTIONAL MATCH (u)-[:USES_DEVICE]->(d:Device)
OPTIONAL MATCH (d)<-[:USES_DEVICE]-(other_dev_u:User)
OPTIONAL MATCH (d)<-[:ORIGINATED_FROM_DEVICE]-(dev_t:Transaction WHERE dev_t.is_fraud = true)

// 2. IP sharing & fraud count
OPTIONAL MATCH (u)-[:USES_IP]->(ip:IPAddress)
OPTIONAL MATCH (ip)<-[:USES_IP]-(other_ip_u:User)
OPTIONAL MATCH (ip)<-[:ORIGINATED_FROM_IP]-(ip_t:Transaction WHERE ip_t.is_fraud = true)

// 3. Merchant connectivity
OPTIONAL MATCH (u)-[:TRANSACTED_WITH]->(m:Merchant)

RETURN
    count(DISTINCT other_dev_u) AS shared_device_users,
    count(DISTINCT dev_t) AS device_fraud_txns,
    count(DISTINCT other_ip_u) AS shared_ip_users,
    count(DISTINCT ip_t) AS ip_fraud_txns,
    count(DISTINCT m) AS merchant_count
```

---

### 3.3 Detecting Multi-Account Collusion (Fraud Rings)
```cypher
MATCH (d:Device)<-[:USES_DEVICE]-(u:User)
WITH d, collect(DISTINCT u.id) AS user_ids, count(DISTINCT u) AS user_count
WHERE user_count >= $min_users_per_device
OPTIONAL MATCH (d)<-[:ORIGINATED_FROM_DEVICE]-(t:Transaction)
RETURN
    'Device' AS entity_type,
    d.fingerprint AS entity_key,
    user_ids,
    user_count,
    collect(DISTINCT t.ref) AS txn_refs,
    sum(CASE WHEN t.is_fraud = true THEN t.amount ELSE 0.0 END) AS total_fraud_amount,
    count(CASE WHEN t.is_fraud = true THEN 1 ELSE NULL END) AS fraud_count
ORDER BY fraud_count DESC, user_count DESC
LIMIT $limit
```

---

## 4. Derived Graph Risk Features

The Neo4j layer computes `GraphRiskFeatures` for real-time and investigative consumption:

| Feature Name | Type | Description |
|---|---|---|
| `shared_device_user_count` | `int` | Count of distinct user accounts transacting on the same device hardware |
| `shared_ip_user_count` | `int` | Count of distinct user accounts transacting from the same IP address |
| `shared_device_fraud_count` | `int` | Prior confirmed fraudulent transactions tied to the hardware fingerprint |
| `shared_ip_fraud_count` | `int` | Prior confirmed fraudulent transactions tied to the IP address |
| `associated_merchant_count` | `int` | Distinct merchants the user has transacted with |
| `fraud_ring_size` | `int` | Total connected entities in the user's 2-hop component |
| `is_device_shared` | `bool` | Flag indicating `shared_device_user_count > 1` |
| `is_ip_shared` | `bool` | Flag indicating `shared_ip_user_count > 1` |
| `graph_risk_score` | `float` | Composite heuristic graph risk score $[0.0, 1.0]$ |

---

## 5. REST API Endpoints

Mounted at `/api/v1/graph`:

- **`GET /api/v1/graph/features/{user_id}`**: Retrieves graph identity sharing features and normalized ML features.
- **`GET /api/v1/graph/fraud-rings?min_users=2`**: Discovers active multi-user collusion fraud rings.
- **`GET /api/v1/graph/subgraph/{entity_type}/{entity_id}?depth=2`**: Returns nodes and edges formatted for visual Cytoscape / 3D Force-Graph canvas rendering in the React frontend.
- **`GET /api/v1/graph/health`**: Verifies driver connectivity, query latency, and node entity counts.

---

## 6. Centralized Configuration

Configured in `backend/.env`:
```env
# ── 8. Neo4j Graph Database ──────────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password_placeholder
NEO4J_DATABASE=neo4j
NEO4J_ENABLED=false
```
