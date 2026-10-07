"""
app/repositories/ip_repo.py
─────────────────────────────────────────────────────────────────────────────
IP Address entity repository.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import IPAddress
from app.repositories.base_repo import BaseRepository


class IPAddressRepository(BaseRepository[IPAddress]):
    def __init__(self, db: Session):
        super().__init__(IPAddress, db)

    def get_by_ip(self, ip_str: str) -> Optional[IPAddress]:
        return self.db.query(IPAddress).filter(IPAddress.ip_address == ip_str).first()

    def get_or_create(
        self,
        ip_str: Optional[str],
        country: Optional[str] = None,
        city: Optional[str] = None,
        is_vpn: bool = False,
        is_tor: bool = False,
    ) -> Optional[IPAddress]:
        if not ip_str or ip_str in ("0.0.0.0", ""):
            return None
        ip_rec = self.get_by_ip(ip_str)
        now = datetime.now(timezone.utc)
        if not ip_rec:
            ip_rec = IPAddress(
                id=uuid.uuid4(),
                ip_address=ip_str,
                geo_country=country,
                geo_city=city,
                is_vpn=is_vpn,
                is_tor=is_tor,
                reputation_score=0.8 if (is_tor or is_vpn) else 0.0,
                last_checked_at=now,
            )
            self.db.add(ip_rec)
            self.db.flush()
        else:
            ip_rec.last_checked_at = now
            if is_vpn:
                ip_rec.is_vpn = True
            if is_tor:
                ip_rec.is_tor = True
            self.db.flush()
        return ip_rec
