import sys

core_modules = [
    "fastapi", "uvicorn", "sqlalchemy", "psycopg2", "alembic",
    "redis", "kafka", "jose", "bcrypt", "pydantic",
    "pydantic_settings", "sklearn", "xgboost",
    "shap", "joblib", "numpy", "pandas", "scipy",
    "httpx", "dotenv"
]

optional_modules = ["loguru", "groq"]

failed = []
print("Verifying core backend runtime module imports:")
for mod in core_modules:
    try:
        __import__(mod)
        print(f"  [OK] {mod}")
    except Exception as e:
        print(f"  [FAIL] {mod}: {e}")
        failed.append(mod)

for mod in optional_modules:
    try:
        __import__(mod)
        print(f"  [OK (optional)] {mod}")
    except Exception as e:
        print(f"  [INFO] {mod} optional module not present: {e}")

if failed:
    print(f"\nImport verification failed for required modules: {failed}")
    sys.exit(1)
else:
    print("\nAll required core backend dependencies imported successfully!")
