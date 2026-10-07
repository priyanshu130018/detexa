"""
app/repositories/model_repo.py
─────────────────────────────────────────────────────────────────────────────
ModelMetadata repository for AI model versions and evaluation registry.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import ModelMetadata
from app.repositories.base_repo import BaseRepository


class ModelMetadataRepository(BaseRepository[ModelMetadata]):
    def __init__(self, db: Session):
        super().__init__(ModelMetadata, db)

    def get_by_name_and_version(self, model_name: str, version: str) -> Optional[ModelMetadata]:
        return (
            self.db.query(ModelMetadata)
            .filter(ModelMetadata.model_name == model_name, ModelMetadata.version == version)
            .first()
        )

    def get_or_create(
        self,
        model_name: str,
        version: str,
        algorithm: str,
        threshold: float = 0.50,
        metrics: Optional[dict] = None,
    ) -> ModelMetadata:
        record = self.get_by_name_and_version(model_name, version)
        if not record:
            record = ModelMetadata(
                id=uuid.uuid4(),
                model_name=model_name,
                version=version,
                algorithm=algorithm,
                threshold=threshold,
                is_active=True,
                metrics=metrics or {},
                trained_at=datetime.now(timezone.utc),
            )
            self.db.add(record)
            self.db.flush()
        return record

    def list_active(self) -> List[ModelMetadata]:
        return self.db.query(ModelMetadata).filter(ModelMetadata.is_active == True).all()
