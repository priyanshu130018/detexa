import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import engine
from sqlalchemy import inspect, text

inspector = inspect(engine)
tables = inspector.get_table_names()
print("Tables in database:", tables)

with engine.connect() as conn:
    for t in tables:
        count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"  {t}: {count} rows")
