"""
app/feature_store/serializer.py
─────────────────────────────────────────────────────────────────────────────
Serialization utilities for Redis Feature Store.
Handles UUIDs, datetimes, decimals, sets, dataclasses, and Pydantic models.
"""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any, Dict, Optional
import uuid


class FeatureJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder handling complex Python primitives for Redis storage."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return super().default(obj)


class FeatureSerializer:
    """Reusable serialization and deserialization helper for Redis values."""

    @staticmethod
    def dumps(obj: Any) -> str:
        """Serializes Python object to JSON string."""
        return json.dumps(obj, cls=FeatureJSONEncoder, separators=(",", ":"))

    @staticmethod
    def loads(raw_str: Optional[str]) -> Optional[Any]:
        """Safely deserializes JSON string back to Python object."""
        if not raw_str:
            return None
        try:
            return json.loads(raw_str)
        except (ValueError, TypeError):
            return raw_str

    @staticmethod
    def encode_dict_for_hash(data: Dict[str, Any]) -> Dict[str, str]:
        """Encodes all values in a dictionary into strings for Redis HSET."""
        encoded: Dict[str, str] = {}
        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                encoded[k] = str(v)
            else:
                encoded[k] = FeatureSerializer.dumps(v)
        return encoded

    @staticmethod
    def decode_hash_dict(raw_hash: Dict[str, str]) -> Dict[str, Any]:
        """Decodes string values from Redis HGETALL back to appropriate types."""
        decoded: Dict[str, Any] = {}
        for k, v in raw_hash.items():
            if v.isdigit():
                decoded[k] = int(v)
            elif v in ("True", "true"):
                decoded[k] = True
            elif v in ("False", "false"):
                decoded[k] = False
            else:
                try:
                    decoded[k] = float(v)
                except ValueError:
                    decoded[k] = FeatureSerializer.loads(v)
        return decoded
