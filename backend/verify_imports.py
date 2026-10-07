import sys

modules = [
    "fastapi", "uvicorn", "sqlalchemy", "psycopg2", "alembic",
    "redis", "neo4j", "kafka", "jose", "bcrypt", "pydantic",
    "pydantic_settings", "sklearn", "xgboost", "imblearn",
    "shap", "joblib", "numpy", "pandas", "scipy", "loguru",
    "httpx", "faker", "pytest", "dotenv"
]

failed = []
for mod in modules:
    try:
        __import__(mod)
        print(f"  [OK] {mod}")
    except Exception as e:
        print(f"  [FAIL] {mod}: {e}")
        failed.append(mod)

if failed:
    print(f"\nImport verification failed for: {failed}")
    sys.exit(1)
else:
    print("\nAll required backend dependencies imported successfully 100%!")
