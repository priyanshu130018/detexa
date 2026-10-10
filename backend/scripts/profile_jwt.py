import time
from jose import jwt
from app.core.config import settings

print("Secret key:", settings.secret_key)
print("Algorithm:", settings.algorithm)

for i in range(5):
    t_start = time.perf_counter()
    token = jwt.encode({"sub": "123"}, settings.secret_key, algorithm=settings.algorithm)
    print(f"jose encode run {i+1}: {(time.perf_counter() - t_start)*1000:.2f} ms")

print("\nTesting decode:")
for i in range(5):
    t_start = time.perf_counter()
    decoded = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    print(f"jose decode run {i+1}: {(time.perf_counter() - t_start)*1000:.2f} ms")
