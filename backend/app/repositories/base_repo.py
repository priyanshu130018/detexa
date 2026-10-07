"""
app/repositories/base_repo.py
─────────────────────────────────────────────────────────────────────────────
Generic Base Repository providing typed CRUD operations and query building.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: Union[uuid.UUID, str]) -> Optional[ModelType]:
        if isinstance(id, str):
            try:
                id = uuid.UUID(id)
            except ValueError:
                return None
        return self.db.query(self.model).filter(self.model.id == id).first()

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None,
    ) -> List[ModelType]:
        q = self.db.query(self.model)
        if order_by is not None:
            q = q.order_by(order_by)
        return q.offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(func.count(self.model.id)).scalar() or 0

    def create(self, obj_in: ModelType, flush: bool = False) -> ModelType:
        self.db.add(obj_in)
        if flush:
            self.db.flush()
        return obj_in

    def update(self, db_obj: ModelType, update_data: Dict[str, Any], flush: bool = False) -> ModelType:
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        if flush:
            self.db.flush()
        return db_obj

    def delete(self, id: Union[uuid.UUID, str], flush: bool = False) -> Optional[ModelType]:
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            if flush:
                self.db.flush()
        return obj
