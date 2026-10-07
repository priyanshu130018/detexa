# Detexa Security Policy & Architecture

This document details the security architecture, implemented cryptographic controls, data protection policies, and production hardening recommendations for the Detexa banking fraud prevention platform.

---

## 1. Security Model Overview

Detexa enforces a defense-in-depth security model spanning the application gateway, microservices communication, in-memory caches, graph datastores, and relational persistence layers.

```
┌────────────────────────────────────────────────────────┐
│                   EDGE & NETWORK LAYER                 │
│  - HTTPS / TLS 1.3 Termination                         │
│  - Strict CORS Origin Whitelisting                     │
│  - Parameterized API Validation (Pydantic v2)          │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                IDENTITY & ACCESS CONTROL               │
│  - Stateless JWT Tokens (HMAC-SHA256)                  │
│  - Bcrypt Password Hashing (Salt Rounds = 12)          │
│  - Role-Based Access Control (Analyst / Admin / API)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                DATA PROTECTION & STORAGE               │
│  - Parameterized ORM Queries (SQLAlchemy 2.0)          │
│  - SSL Encrypted Neon PostgreSQL (sslmode=require)     │
│  - Ephemeral Redis Feature TTLs                        │
│  - Tokenized Hardware Fingerprints & Masked IPs        │
└────────────────────────────────────────────────────────┘
```

---

## 2. Implemented Security Controls

### 2.1 Authentication & Token Handling
- **JWT Authentication:** Uses stateless JSON Web Tokens signed with HMAC-SHA256 (`HS256`).
- **Token Expiration:** Access tokens carry a configurable Time-To-Live (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 60 minutes).
- **Password Hashing:** Passwords are never stored in plaintext. They are salted and hashed using `bcrypt` (12 rounds) via `passlib.context.CryptContext`.
- **OAuth2 Standard:** Standard OAuth2 password flow implemented at `/api/v1/auth/login`.

### 2.2 API Input Validation & Sanitization
- **Strict Pydantic Schemas:** All incoming request payloads are strictly parsed and validated against Pydantic models. Malformed, excess, or type-mismatched parameters are rejected with `422 Unprocessable Entity` before reaching business logic.
- **SQL Injection Prevention:** All relational queries utilize SQLAlchemy 2.0 ORM expressions and bound parameter substitutions; raw string concatenations are prohibited.
- **No Path Traversal:** File uploads (such as batch CSV scoring) are processed purely in-memory (`UploadFile.file` / `BytesIO`) without writing temporary files to arbitrary host filesystem locations.

### 2.3 CORS (Cross-Origin Resource Sharing)
- CORS middleware is explicitly configured with an origin whitelist defined in `settings.cors_origins` (e.g. `http://localhost:5173`). Wildcard `*` origins are disabled in production mode.

### 2.4 Database & Transport Encryption
- **PostgreSQL / Neon Cloud:** Enforces TLS encrypted transit using `sslmode=require`.
- **Sensitive Fields:** Cardholder data, PINs, and full PANs are never ingested or stored. Detexa operates on normalized PCA components, tokenized reference IDs, and masked device identifiers.

### 2.5 In-Memory & Graph Security
- **Redis TTL Hygiene:** Sliding window counters and velocity keys in Redis use strict TTL expirations (1m to 24h) to prevent unbounded memory growth and data lingering.
- **Neo4j Access:** Secured with role-based username/password authentication over encrypted Bolt protocol.

---

## 3. Recommended Production Hardening Checklist

The following controls are recommended for enterprise production deployment:

| Category | Recommended Control | Purpose |
|---|---|---|
| **Edge / Network** | TLS 1.3 Reverse Proxy (Nginx / Cloudflare) | Encrypts all public web and WebSocket traffic; terminates SSL. |
| **DDoS & Rate Limiting**| Redis-backed Rate Limiting (e.g. 100 req/min per IP) | Protects API from brute force and denial of service attacks. |
| **Secrets Management** | AWS Secrets Manager / HashiCorp Vault | Injects `SECRET_KEY`, database passwords, and API keys without local `.env` files. |
| **Kafka Security** | SASL/SCRAM Authentication + TLS | Encrypts and authenticates inter-broker streaming communications. |
| **Container Hardening** | Run as non-root user (`USER appuser`) | Prevents container breakout vulnerabilities in Docker containers. |
| **Vulnerability Scanning**| Trivy / Snyk / Dependabot CI Pipeline | Automatically scans Python (`pip-audit`) and npm (`npm audit`) dependencies. |

---

## 4. Sensitive Data Handling Guidelines

1. **Cardholder Data (PCI-DSS):**
   - Do **NOT** send 16-digit credit card Primary Account Numbers (PAN), CVVs, or plaintext PINs to Detexa.
   - Use tokenized reference IDs (`transaction_ref`, `user_id`, `merchant_id`).
2. **Behavioral Biometrics:**
   - Raw keystroke logs are aggregated into typing cadence speeds ($WPM$ / chars per second) to preserve user privacy.
3. **Geo-IP Telemetry:**
   - IP addresses are checked against VPN/Tor exit lists and aggregated to country/region level.

---

## 5. Security Vulnerability Reporting

If you identify a security vulnerability in the Detexa codebase:
1. **Do NOT open a public GitHub issue.**
2. Report the vulnerability privately to the Detexa Security Response Team at `security@detexa.io`.
3. Include detailed reproduction steps, environment details, and a proof-of-concept payload if applicable.
4. The team will acknowledge receipt within 48 hours and provide a fix timeline.
