"""
app/feature_store/keys.py
─────────────────────────────────────────────────────────────────────────────
Standardized Redis key namespacing and builders for the real-time feature store.
Ensures zero key collisions and clear TTL boundaries.
"""


class FeatureKeyBuilder:
    """Builder for hierarchical Redis keys in the Detexa Feature Store."""

    PREFIX = "detexa:fs"

    @classmethod
    def transactions_zset_key(cls, user_key: str) -> str:
        """Sorted Set storing timestamped transaction events (Score = Epoch Timestamp)."""
        return f"{cls.PREFIX}:zset:txns:{user_key}"

    @classmethod
    def failed_auth_zset_key(cls, user_key: str) -> str:
        """Sorted Set storing timestamped failed authentication/authorization events."""
        return f"{cls.PREFIX}:zset:fails:{user_key}"

    @classmethod
    def merchants_set_key(cls, user_key: str) -> str:
        """Set of recent merchant names seen for this entity."""
        return f"{cls.PREFIX}:set:merch:{user_key}"

    @classmethod
    def categories_set_key(cls, user_key: str) -> str:
        """Set of recent merchant categories seen for this entity."""
        return f"{cls.PREFIX}:set:cat:{user_key}"

    @classmethod
    def devices_set_key(cls, user_key: str) -> str:
        """Set of recent device fingerprints seen for this entity."""
        return f"{cls.PREFIX}:set:dev:{user_key}"

    @classmethod
    def ips_set_key(cls, user_key: str) -> str:
        """Set of recent IP addresses seen for this entity."""
        return f"{cls.PREFIX}:set:ip:{user_key}"

    @classmethod
    def countries_set_key(cls, user_key: str) -> str:
        """Set of recent countries seen for this entity."""
        return f"{cls.PREFIX}:set:geo:{user_key}"

    @classmethod
    def counters_hash_key(cls, user_key: str) -> str:
        """Hash storing cumulative failure counts, alert counters, and aggregates."""
        return f"{cls.PREFIX}:hash:counters:{user_key}"

    @classmethod
    def latest_state_hash_key(cls, user_key: str) -> str:
        """Hash storing the most recent transaction metadata (device, IP, merchant, amount)."""
        return f"{cls.PREFIX}:hash:latest:{user_key}"

    @classmethod
    def snapshot_key(cls, user_key: str) -> str:
        """Key storing cached serialized HotFeatureVector snapshot."""
        return f"{cls.PREFIX}:snap:{user_key}"

    @classmethod
    def user_pattern(cls, user_key: str) -> str:
        """Wildcard pattern matching all keys for a given user."""
        return f"{cls.PREFIX}:*:{user_key}"
