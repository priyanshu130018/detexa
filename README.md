# 🛡️ Detexa – AI-Powered Fraud Detection Platform

> Production-ready fraud detection system with credit-card fraud scoring, behavioural anomaly detection, SHAP explainability, and a modern dark-mode Streamlit dashboard.

---

## 🗂️ Project Structure

```
detexa/
├── api/                        # FastAPI backend
│   ├── main.py                 # App factory & lifespan hooks
│   ├── middleware/
│   │   └── auth_middleware.py  # JWT Bearer dependency
│   └── routers/
│       ├── auth.py             # /auth/register, /auth/login, /auth/me
│       ├── predict.py          # /predict/credit, /predict/behavior
│       └── alerts.py           # /alerts, /alerts/stats, /alerts/transactions
│
├── core/                       # Shared configuration & utilities
│   ├── config.py               # Pydantic-Settings (reads .env)
│   ├── security.py             # JWT + bcrypt helpers
│   └── logging.py              # Loguru structured logger
│
├── database/                   # SQLAlchemy ORM layer
│   ├── db.py                   # Engine, session factory, get_db dependency
│   └── models.py               # users, transactions, behavior_logs, alerts, prediction_logs
│
├── models/                     # Pydantic v2 request / response schemas
│   └── schemas.py
│
├── services/                   # Business logic layer
│   ├── auth_service.py
│   ├── fraud_service.py
│   ├── behavior_service.py
│   └── alert_service.py
│
├── ml/                         # Machine learning
│   ├── models/
│   │   ├── credit_fraud_model.py   # XGBoost / RF wrapper + SHAP
│   │   └── behavior_model.py       # Isolation Forest wrapper
│   └── pipelines/
│       └── feature_engineering.py  # Credit & behaviour feature pipelines
│
├── dashboard/                  # Streamlit frontend
│   ├── app.py                  # Entry point – auth gate + sidebar nav
│   ├── api_client.py           # HTTP client for backend calls
│   └── pages/
│       ├── login.py            # Login / Register UI
│       ├── overview.py         # Main dashboard – KPIs, daily/monthly charts
│       ├── transactions.py     # Filterable transaction table
│       ├── alerts_page.py      # Alert management
│       ├── predict_page.py     # Live prediction testing
│       └── behavior_page.py    # Behaviour analytics
│
├── scripts/
│   ├── train_models.py         # Train credit + behaviour models
│   └── seed_data.py            # Populate DB with demo data
│
├── alembic/                    # Database migrations
│   └── env.py
│
├── docker/
│   ├── Dockerfile.api
│   └── Dockerfile.dashboard
│
├── tests/                      # Pytest test suite (add your tests here)
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## ⚡ Quick Start

### 1 – Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+ (optional – used for caching)
- Docker + Docker Compose (for containerised deployment)

### 2 – Local Setup

```bash
# Clone and enter the project
cd detexa

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, etc.

# Create DB tables
python -c "from database.db import engine; from database.models import Base; Base.metadata.create_all(engine)"

# Train ML models (uses synthetic data if Kaggle CSV not supplied)
python scripts/train_models.py

# (Optional) Supply the real Kaggle dataset for better accuracy:
# python scripts/train_models.py --data /path/to/creditcard.csv

# Seed demo data
python scripts/seed_data.py

# Start FastAPI backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# In a second terminal, start Streamlit dashboard
streamlit run dashboard/app.py
```

Open:
- **Dashboard:** http://localhost:8501
- **API docs:** http://localhost:8000/docs
- **Demo login:** `admin@detexa.io` / `Admin@1234`

---

### 3 – Docker Compose (full stack)

```bash
docker-compose up --build
```

Services started:
| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| Redis | 6379 |
| FastAPI API | 8000 |
| Streamlit Dashboard | 8501 |

---

## 🤖 ML Models

### Credit Card Fraud Detection
- **Dataset:** [Kaggle Credit Card Fraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **Algorithm:** XGBoost (falls back to Random Forest if XGBoost not available)
- **Imbalance handling:** SMOTE oversampling
- **Explainability:** SHAP TreeExplainer (top-10 feature contributions per prediction)
- **AUC-ROC:** ~0.98+ on the real Kaggle dataset

### Behavioural Anomaly Detection
- **Algorithm:** Isolation Forest
- **Features:** login hour, typing speed, mouse velocity, VPN/TOR flags, device changes, failed logins
- **Output:** Anomaly score [0, 1] (higher = more suspicious)

### Risk Levels
| Score | Level |
|-------|-------|
| ≥ 0.75 | 🔴 High |
| ≥ 0.50 | 🟡 Medium |
| < 0.50 | 🟢 Low |

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT token |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/predict/credit` | Credit fraud score |
| POST | `/api/v1/predict/behavior` | Behaviour anomaly score |
| GET | `/api/v1/alerts` | List alerts |
| PUT | `/api/v1/alerts/{id}/status` | Update alert status |
| GET | `/api/v1/alerts/stats` | Dashboard statistics |
| GET | `/api/v1/alerts/transactions` | Transaction list |

---

## 🗄️ Database Schema

```
users              – id, name, email, mobile, hashed_password, is_admin
transactions       – id, user_id, amount, V1–V28, merchant, fraud_score, risk_level, is_fraud
behavior_logs      – id, user_id, session_id, ip_address, device_fingerprint, anomaly_score
alerts             – id, user_id, transaction_id, alert_type, risk_level, score, status
prediction_logs    – id, endpoint, fraud_score, latency_ms, model_version
```

---

## 📊 Dashboard Pages

| Page | Description |
|------|-------------|
| **Overview** | KPI cards, daily transaction bar chart, monthly report, risk distribution doughnut |
| **Transactions** | Filterable table with fraud row highlighting, CSV export |
| **Alerts** | Alert cards with status management, timeline area chart |
| **Live Predict** | Interactive credit fraud + behaviour prediction forms with score gauge |
| **Behaviour** | IP/device analytics, country heatmap, anomaly histogram |

---

## 🔐 Authentication

- JWT Bearer tokens (HS256)
- bcrypt password hashing
- Access tokens expire after 60 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)

---

## 🚀 Production Checklist

- [ ] Change `SECRET_KEY` in `.env` (min 32 chars, random)
- [ ] Use Alembic migrations instead of `create_all`
- [ ] Train on real Kaggle dataset: `python scripts/train_models.py --data creditcard.csv`
- [ ] Enable Redis caching (`REDIS_URL` in `.env`)
- [ ] Set `APP_ENV=production`
- [ ] Configure reverse proxy (Nginx) in front of both services
- [ ] Set up log rotation and monitoring (Prometheus / Grafana)
- [ ] Enable HTTPS (TLS termination at Nginx or load balancer)

---

## 📄 License

MIT – use freely, attribute kindly.
