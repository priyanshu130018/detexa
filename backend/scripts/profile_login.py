import time
import uuid
from app.db.session import SessionLocal
from app.db.models import User, AuditLog
from app.core.security import verify_password, create_access_token
from datetime import datetime, timezone

def profile():
    t0 = time.perf_counter()
    db = SessionLocal()
    t1 = time.perf_counter()

    user = db.query(User).filter(User.email == "admin@detexa.io").first()
    t2 = time.perf_counter()

    valid = verify_password("Admin@1234", user.hashed_password)
    t3 = time.perf_counter()

    user.last_login = datetime.now(timezone.utc)
    audit = AuditLog(
        id=uuid.uuid4(),
        user_id=user.id,
        action="USER_LOGGED_IN",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    t4 = time.perf_counter()

    db.commit()
    t5 = time.perf_counter()

    token = create_access_token({"sub": str(user.id), "email": user.email, "is_admin": user.is_admin})
    t6 = time.perf_counter()

    db.close()
    t7 = time.perf_counter()

    print(f"Session creation: {(t1-t0)*1000:.2f} ms")
    print(f"User query:       {(t2-t1)*1000:.2f} ms")
    print(f"Password verify:  {(t3-t2)*1000:.2f} ms")
    print(f"Audit prep:       {(t4-t3)*1000:.2f} ms")
    print(f"DB commit:        {(t5-t4)*1000:.2f} ms")
    print(f"JWT generation:   {(t6-t5)*1000:.2f} ms")
    print(f"DB close:         {(t7-t6)*1000:.2f} ms")
    print(f"Total:            {(t7-t0)*1000:.2f} ms")

if __name__ == "__main__":
    for i in range(3):
        print(f"--- Iteration {i+1} ---")
        profile()
