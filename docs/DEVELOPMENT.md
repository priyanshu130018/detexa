# Detexa Developer Guide

This guide covers local development workflows, environment configuration, database migrations, model training/retraining pipelines, Docker orchestration, and debugging techniques for the Detexa platform.

---

## 1. Prerequisites

Ensure the following tools are installed on your workstation:
- **Docker & Docker Compose:** Docker Engine 24.0+ / Docker Compose v2.20+
- **Python:** Version 3.11.x
- **Node.js & npm:** Node 18.x or 20.x, npm 9.x+
- **Git:** Version 2.30+

---

## 2. Environment Configuration (`.env`)

Detexa uses a single unified `.env` file at the repository root. Ensure the file contains:

```env
# Application Settings
APP_NAME=Detexa
APP_ENV=development
APP_VERSION=2.0.0
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production-min-32-chars-long
API_V1_STR=/api/v1
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]

# PostgreSQL / Neon Database
DATABASE_URL=postgresql://neondb_owner:npg_Xk0yI6rUeLms@ep-ancient-sky-a87l140z-pooler.eastus2.azure.neon.tech/neondb?sslmode=require
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis Feature Store
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_ENABLED=True

# Apache Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_ENABLED=True
KAFKA_TOPIC_TRANSACTIONS=transactions.raw
KAFKA_TOPIC_ALERTS=fraud.alerts
KAFKA_TOPIC_METRICS=metrics.stream

# Neo4j Graph Database
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=detexa_secret_password
NEO4J_ENABLED=True

# Decision Engine Policy Thresholds
THRESHOLD_ALLOW=0.30
THRESHOLD_CHALLENGE=0.70
THRESHOLD_REVIEW=0.90
THRESHOLD_BLOCK=0.90

# ML Model Paths
CREDIT_MODEL_PATH=models/credit_fraud_xgboost.joblib
CREDIT_SCALER_PATH=models/credit_fraud_scaler.joblib
BEHAVIOR_MODEL_PATH=models/behavior_isolation_forest.joblib
BEHAVIOR_SCALER_PATH=models/behavior_scaler.joblib
```

> **Note:** When running the backend directly on your host machine (outside Docker), update container hostnames (`redis`, `kafka`, `neo4j`) to `localhost` and use host-mapped ports (`localhost:6379`, `localhost:9094`, `localhost:7687`).

---

## 3. Docker Workflows

### 3.1 Start Stack
```bash
# Build and start all services in detached mode
docker compose up --build -d
```

### 3.2 View Logs
```bash
# Follow logs for all services
docker compose logs -f

# Follow specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f kafka
```

### 3.3 Check Status & Health
```bash
docker compose ps
```

### 3.4 Stop Stack
```bash
# Stop containers (preserves volume data)
docker compose down

# Stop containers and remove volumes (clean slate)
docker compose down -v
```

---

## 4. Local Backend Development

To run the backend on the host machine without Docker:

### 4.1 Setup Virtual Environment
```bash
cd backend
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4.2 Start Supporting Services
Run only supporting storage and streaming infrastructure via Docker:
```bash
docker compose up -d redis kafka neo4j zookeeper
```

### 4.3 Run Database Migrations
```bash
cd backend
alembic upgrade head
```

### 4.4 Start FastAPI Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger UI will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 5. Local Frontend Development

### 5.1 Install Dependencies
```bash
cd frontend
npm install
```

### 5.2 Start Vite Dev Server
```bash
npm run dev
```
The React development server runs at [http://localhost:5173](http://localhost:5173).

### 5.3 Production Build & Typecheck
```bash
npm run build
```
Runs `tsc` (TypeScript compiler) followed by `vite build`.

---

## 6. Database Migrations (Alembic)

All schema changes are version-controlled via Alembic in `backend/alembic/`.

### 6.1 Apply Latest Migrations
```bash
cd backend
alembic upgrade head
```

### 6.2 Create a New Migration
When modifying SQLAlchemy models in `backend/app/models/`:
```bash
cd backend
alembic revision --autogenerate -m "describe_schema_change"
```

### 6.3 Roll Back a Migration
```bash
cd backend
alembic downgrade -1
```

> **Important:** The Docker backend container entrypoint automatically executes `alembic upgrade head` on startup before launching FastAPI.

---

## 7. Dataset Placement & Model Training

### 7.1 Dataset Placement
Detexa utilizes the Indian banking transaction dataset: `indian_banking_transactions.csv`.

1. Download the transaction dataset from Kaggle.
2. Ensure directory `backend/data/raw/` exists:
   ```bash
   mkdir -p backend/data/raw
   ```
3. Place the CSV file at:
   ```text
   backend/data/raw/indian_banking_transactions.csv
   ```

### 7.2 Train Indian Banking Fraud Model (XGBoost)
To train and export new model artifacts:
```bash
python backend/scripts/train_banking_fraud_model.py
```
This generates:
- `backend/app/ml/saved/banking_fraud_pipeline.pkl` (Trained pipeline)
- `backend/app/ml/saved/banking_fraud_pipeline_metadata.json` (Pipeline metadata)
- `backend/app/ml/saved/feature_metadata.json` (Feature schema)

### 7.3 Train Behavioral Anomaly Model (Isolation Forest)
```bash
cd backend
python -m app.ml.train_behavior_model
```
This generates:
- `backend/models/behavior_isolation_forest.joblib`
- `backend/models/behavior_scaler.joblib`

---

## 8. Adding or Changing Features in Canonical Schema

When adding new features to the 61-feature canonical vector:
1. **Schema Definition:** Update `backend/app/services/feature_service.py` to register the new feature name under its respective group (`transaction`, `temporal`, `behavioral`, `redis_hot`, `graph_risk`).
2. **Feature Extractor:** Implement feature extraction logic in `backend/app/ml/feature_pipeline.py`.
3. **Model Retraining:** Re-fit the scaler and booster using `app.ml.train_credit_model`.
4. **Frontend Alignment:** Verify that feature descriptions and charts in `ModelStatisticsPage.tsx` reflect the updated schema count.

---

## 9. Troubleshooting & Debugging

| Issue | Cause | Resolution |
|---|---|---|
| `NoBrokersAvailable` | Backend cannot connect to Kafka | Ensure `KAFKA_BOOTSTRAP_SERVERS` is set to `kafka:9092` (inside Docker) or `localhost:9094` (on host). |
| `DuplicateObject: type "risklevel" already exists` | Alembic enum collision in PostgreSQL | Safe enum check is implemented in `0001_initial_neon_schema.py`. Ensure migration is executed via `alembic upgrade head`. |
| `Redis Connection Refused` | Redis container not running | Check `docker compose ps` and verify port `6379`. |
| `Neo4j Unauthorized` | Password mismatch | Verify `NEO4J_PASSWORD` in `.env` matches container initialization credentials (`detexa_secret_password`). |
| `Theme Flashing on Reload` | Theme script not executing in `<head>` | Verify `index.html` inline script checks `localStorage.getItem('detexa_theme')` before body render. |
