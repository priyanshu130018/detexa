"""
backend/app/db/migrate_enums.py
Ensures PostgreSQL enum types support all required application values.
"""
import os
import psycopg2

def migrate_enums():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    conn.autocommit = True
    cur = conn.cursor()

    queries = [
        "ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'CHALLENGE';",
        "ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'challenge';",
        "ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'allow';",
        "ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'review';",
        "ALTER TYPE decisiontype ADD VALUE IF NOT EXISTS 'block';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'OPEN';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'REVIEWED';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'RESOLVED';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'FALSE_POSITIVE';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'open';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'reviewed';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'resolved';",
        "ALTER TYPE alertstatus ADD VALUE IF NOT EXISTS 'false_positive';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'Low';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'Medium';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'High';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'Critical';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'LOW';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'MEDIUM';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'HIGH';",
        "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'CRITICAL';",
    ]

    for q in queries:
        try:
            cur.execute(q)
            print(f"Executed: {q}")
        except Exception as e:
            print(f"Error on '{q}': {e}")

    cur.close()
    conn.close()
    print("Enum migration completed successfully!")

if __name__ == "__main__":
    migrate_enums()
