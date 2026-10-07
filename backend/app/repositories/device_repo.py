"""
app/repositories/device_repo.py
─────────────────────────────────────────────────────────────────────────────
Device entity repository.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import Device
from app.repositories.base_repo import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    def __init__(self, db: Session):
        super().__init__(Device, db)

    def get_by_fingerprint(self, fingerprint: str, user_id: Optional[uuid.UUID] = None) -> Optional[Device]:
        q = self.db.query(Device).filter(Device.device_fingerprint == fingerprint)
        if user_id:
            q = q.filter(Device.user_id == user_id)
        return q.first()

    def get_or_create(
        self, user_id: Optional[uuid.UUID], fingerprint: Optional[str], user_agent: Optional[str] = None
    ) -> Optional[Device]:
        if not fingerprint:
            return None
        device = self.get_by_fingerprint(fingerprint, user_id)
        now = datetime.now(timezone.utc)
        if not device:
            device = Device(
                id=uuid.uuid4(),
                user_id=user_id,
                device_fingerprint=fingerprint,
                user_agent=user_agent,
                is_trusted=True,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(device)
            self.db.flush()
        else:
            device.last_seen_at = now
            if user_agent and not device.user_agent:
                device.user_agent = user_agent
            self.db.flush()
        return device
