import os
import sys

from app.db.session import SessionLocal, engine
from sqlalchemy import text, inspect

def main():
    db = SessionLocal()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("=== DATABASE TABLE ROW COUNTS ===")
    total_rows = {}
    for t in sorted(tables):
        count = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        total_rows[t] = count
        print(f"Table: {t:25} | Row Count: {count:5}")

    print("\n=== FOREIGN KEY & RELATIONSHIP INTEGRITY ===")
    unlinked_pred = db.execute(text("SELECT COUNT(*) FROM fraud_predictions WHERE transaction_id NOT IN (SELECT id FROM transactions)")).scalar()
    print(f"Predictions without valid transaction: {unlinked_pred}")

    unlinked_alerts = db.execute(text("SELECT COUNT(*) FROM fraud_alerts WHERE transaction_id IS NOT NULL AND transaction_id NOT IN (SELECT id FROM transactions)")).scalar()
    print(f"Alerts without valid transaction: {unlinked_alerts}")

    unlinked_txn_users = db.execute(text("SELECT COUNT(*) FROM transactions WHERE user_id NOT IN (SELECT id FROM users)")).scalar()
    print(f"Transactions without valid user: {unlinked_txn_users}")

    unlinked_txn_merchants = db.execute(text("SELECT COUNT(*) FROM transactions WHERE merchant_id NOT IN (SELECT id FROM merchants)")).scalar()
    print(f"Transactions without valid merchant: {unlinked_txn_merchants}")

    # Standardize any older alert descriptions that had '$'
    db.execute(text("UPDATE fraud_alerts SET description = REPLACE(description, '$', '₹') WHERE description LIKE '%$%'"))
    db.commit()

    print("\n=== TRANSACTION CURRENCY & REGIONS ===")
    currencies = db.execute(text("SELECT currency, COUNT(*) FROM transactions GROUP BY currency")).fetchall()
    print(f"Currencies in DB: {[dict(c._mapping) for c in currencies]}")

    states = db.execute(text("SELECT state, COUNT(*) FROM transactions GROUP BY state ORDER BY COUNT(*) DESC")).fetchall()
    print(f"States in DB: {[dict(s._mapping) for s in states]}")

    payment_types = db.execute(text("SELECT transaction_type, COUNT(*) FROM transactions GROUP BY transaction_type")).fetchall()
    print(f"Payment Methods in DB: {[dict(p._mapping) for p in payment_types]}")

    print("\n=== ALERT INTEGRITY & STATS ===")
    alerts = db.execute(text("SELECT id, risk_level, score, status, description, transaction_id FROM fraud_alerts ORDER BY score DESC")).fetchall()
    print(f"Total Fraud Alerts: {len(alerts)}")
    for i, a in enumerate(alerts, 1):
        m = dict(a._mapping)
        print(f"  Alert #{i:2d} | Score: {m['score']:.4f} | Risk: {m['risk_level']:6} | Status: {m['status']:8} | Txn: {str(m['transaction_id'])[:8]}... | {m['description']}")

    print("\n=== ACTIVE ML MODEL METADATA ===")
    models = db.execute(text("SELECT model_name, version, is_active, algorithm, threshold, metrics FROM model_metadata")).fetchall()
    for m in models:
        print(f"  Model: {m.model_name} (v{m.version}) | Algorithm: {m.algorithm} | Active: {m.is_active} | Threshold: {m.threshold}")

    db.close()

if __name__ == "__main__":
    main()
