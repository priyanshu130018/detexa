"""
app/repositories/merchant_repo.py
─────────────────────────────────────────────────────────────────────────────
Merchant entity repository.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import Merchant
from app.repositories.base_repo import BaseRepository


class MerchantRepository(BaseRepository[Merchant]):
    def __init__(self, db: Session):
        super().__init__(Merchant, db)

    def get_by_name(self, name: str) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.name == name).first()

    def get_or_create(self, name: str, category: str = "General", risk_score: float = 0.0) -> Merchant:
        merchant = self.get_by_name(name)
        if not merchant:
            merchant = Merchant(
                id=uuid.uuid4(),
                name=name,
                category=category,
                risk_score=risk_score,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(merchant)
            self.db.flush()
        return merchant
