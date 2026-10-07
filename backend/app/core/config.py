"""
app/core/config.py
─────────────────────────────────────────────────────────────────────────────
Centralized application settings using Pydantic Settings v2.
Reads configuration from environment variables and .env file with validated types.
"""

from functools import lru_cache
import json
from typing import List, Literal, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    # ── 1. Application & Runtime Settings ────────────────────────────────────
    app_name: str = Field(default="Detexa", description="Display name of the application")
    app_version: str = Field(default="2.0.0", description="Semantic version string")
    app_env: Literal["development", "staging", "production", "testing"] = Field(
        default="development", description="Current deployment environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode and verbose tracebacks")
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    log_file_path: str = Field(default="logs/detexa.log", description="Path for disk file logger")
    log_rotation: str = Field(default="10 MB", description="File rotation size")
    log_retention: str = Field(default="30 days", description="Log file retention period")

    # ── 2. API Server & Routing ──────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", description="Host interface for API server binding")
    api_port: int = Field(default=8000, description="Port number for API server binding")
    api_v1_str: str = Field(default="/api/v1", description="Prefix for API version 1 routes")
    docs_url: Optional[str] = Field(default="/docs", description="Swagger UI endpoint path")
    redoc_url: Optional[str] = Field(default="/redoc", description="ReDoc endpoint path")

    # ── 3. CORS Configuration ────────────────────────────────────────────────
    cors_origins: Union[List[str], str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origin domains",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow cookies and auth headers in CORS")
    cors_allow_methods: List[str] = Field(default=["*"], description="Allowed HTTP methods")
    cors_allow_headers: List[str] = Field(default=["*"], description="Allowed HTTP headers")

    # ── 4. Security & JWT Settings ───────────────────────────────────────────
    secret_key: str = Field(
        default="778faf5b1c899317c3c1748aeccea95c3dd6553dd126cc1f344b9cade8de6f17",
        description="Cryptographic secret key for signing JWT tokens",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm (e.g., HS256)")
    access_token_expire_minutes: int = Field(default=120, description="JWT access token expiry in minutes")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiry in days")

    # ── 5. Database (PostgreSQL / Neon Cloud / SQLite) ────────────────────────
    database_url: str = Field(
        default="postgresql://detexa_user:detexa_pass@localhost:5432/detexa_db",
        description="SQLAlchemy database connection URI (supports standard Postgres, Neon, or SQLite)",
    )
    db_pool_size: int = Field(default=10, description="SQLAlchemy connection pool base size")
    db_max_overflow: int = Field(default=20, description="Maximum overflow connections in pool")
    db_pool_pre_ping: bool = Field(default=True, description="Verify connection liveness before checkout")
    db_pool_recycle: int = Field(default=1800, description="Recycle pool connections after N seconds")
    db_echo: bool = Field(default=False, description="Log generated SQL queries to stdout")

    # ── 6. Redis In-Memory Cache & Real-Time Feature Store ──────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI (supports redis://, rediss:// for SSL, or Upstash)",
    )
    redis_enabled: bool = Field(default=True, description="Flag to enable/disable Redis caching and feature store")
    redis_password: Optional[str] = Field(default=None, description="Redis authentication password if not in URL")
    redis_ssl: bool = Field(default=False, description="Enable TLS/SSL for cloud Redis connections")
    redis_pool_max_connections: int = Field(default=50, description="Max simultaneous Redis pool connections")
    redis_socket_timeout: float = Field(default=2.0, description="Redis socket read/write timeout in seconds")
    redis_socket_connect_timeout: float = Field(default=2.0, description="Redis socket connection timeout in seconds")
    redis_cache_ttl_stats: int = Field(default=30, description="Dashboard statistics cache TTL in seconds")
    redis_cache_ttl_predictions: int = Field(default=300, description="Prediction deduplication cache TTL in seconds")
    
    # Feature Store Specific TTLs (seconds)
    redis_fs_ttl_transactions_sec: int = Field(default=86400, description="Sliding window transaction TTL (24h)")
    redis_fs_ttl_failures_sec: int = Field(default=3600, description="Failed auth attempts TTL (1h)")
    redis_fs_ttl_devices_sec: int = Field(default=86400, description="Recent devices TTL (24h)")
    redis_fs_ttl_ips_sec: int = Field(default=86400, description="Recent IP addresses TTL (24h)")
    redis_fs_ttl_merchants_sec: int = Field(default=3600, description="Recent merchants TTL (1h)")
    redis_fs_ttl_counters_sec: int = Field(default=604800, description="Behavioral counters TTL (7 days)")


    # ── 7. Kafka Streaming (Event Bus / Ingestion Pipeline) ──────────────────
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Comma-separated Kafka broker addresses (e.g. Confluent / Upstash / local)",
    )
    kafka_security_protocol: str = Field(default="PLAINTEXT", description="Security protocol (PLAINTEXT, SASL_SSL)")
    kafka_sasl_mechanism: Optional[str] = Field(default="PLAIN", description="SASL mechanism (PLAIN, SCRAM-SHA-256)")
    kafka_sasl_username: Optional[str] = Field(default=None, description="SASL username for Kafka authentication")
    kafka_sasl_password: Optional[str] = Field(default=None, description="SASL password for Kafka authentication")
    kafka_transactions_topic: str = Field(default="detexa.transactions.raw", description="Ingestion topic for card transactions")
    kafka_alerts_topic: str = Field(default="detexa.alerts.high_risk", description="Egress topic for high-risk alerts")
    kafka_consumer_group: str = Field(default="detexa-fraud-engine-group", description="Kafka consumer group ID")
    kafka_client_id: str = Field(default="detexa-backend-v2", description="Kafka client identifier")
    kafka_enabled: bool = Field(default=False, description="Flag to enable Kafka streaming consumers/producers")

    # ── 8. Neo4j Graph Database (Entity Resolution & Fraud Rings) ─────────────
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI (supports bolt://, neo4j://, neo4j+s:// for AuraDB)",
    )
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="neo4j_password_placeholder", description="Neo4j password")
    neo4j_database: str = Field(default="neo4j", description="Target Neo4j database name")
    neo4j_enabled: bool = Field(default=False, description="Flag to enable Neo4j graph traversal engine")

    # ── 9. ML Models & Inference Thresholds ──────────────────────────────────
    model_path: str = Field(default="app/ml/saved", description="Directory path holding serialized .pkl model pipelines")
    banking_model_filename: str = Field(default="banking_fraud_pipeline.pkl", description="Banking fraud classifier filename")
    credit_model_filename: str = Field(default="banking_fraud_pipeline.pkl", description="Legacy alias for fraud classifier filename")
    behavior_model_filename: str = Field(default="behavior_pipeline.pkl", description="Behavior anomaly pipeline filename")
    fraud_threshold: float = Field(default=0.50, description="Fraud probability threshold for MEDIUM risk / alert flag")
    high_risk_threshold: float = Field(default=0.75, description="Fraud probability threshold for HIGH risk")
    batch_inference_max_rows: int = Field(default=5000, description="Max allowed rows for batch CSV scoring")
    shap_top_k_features: int = Field(default=10, description="Number of top SHAP feature contributions to compute")

    # ── 10. Fraud Decision Engine Policy & Configurable Rules ────────────────
    decision_threshold_allow: float = Field(default=0.40, description="Upper score bound for automatic ALLOW")
    decision_threshold_challenge: float = Field(default=0.65, description="Score threshold for CHALLENGE / Step-up MFA")
    decision_threshold_review: float = Field(default=0.85, description="Score threshold for Manual REVIEW")
    rule_max_velocity_1m: int = Field(default=5, description="Burst velocity limit in 1m before BLOCK")
    rule_max_velocity_5m: int = Field(default=12, description="Elevated velocity limit in 5m before CHALLENGE/REVIEW")
    rule_max_failed_auth_5m: int = Field(default=3, description="Failed auth limit in 5m before BLOCK")
    rule_max_amount_deviation: float = Field(default=4.5, description="Deviation multiplier against rolling avg before CHALLENGE")
    rule_max_amount_hard_limit: float = Field(default=10000.0, description="Hard amount limit trigger for REVIEW")
    rule_max_graph_shared_users: int = Field(default=3, description="Max allowed users sharing hardware device before BLOCK")
    rule_max_graph_risk_score: float = Field(default=0.65, description="Max graph topological risk score before CHALLENGE")
    rule_enable_device_change_challenge: bool = Field(default=True, description="Enforce CHALLENGE on new device for large txns")
    rule_enable_ip_hopping_challenge: bool = Field(default=True, description="Enforce CHALLENGE on IP hopping")
    rule_off_peak_night_threshold: float = Field(default=500.0, description="Nocturnal transaction limit triggering CHALLENGE")

    # ── 11. Groq LLM Explanation Layer ───────────────────────────────────────
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key for natural language fraud explanations")
    groq_model: str = Field(default="openai/gpt-oss-20b", description="Groq LLM model name")
    groq_timeout_seconds: float = Field(default=4.0, description="HTTP request timeout for Groq API calls")
    groq_max_retries: int = Field(default=1, description="Max retries for Groq API call")

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
