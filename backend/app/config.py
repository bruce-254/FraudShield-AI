"""Application configuration. All secrets/URLs come from the environment."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FraudShield AI"
    environment: str = "development"

    # PostgreSQL in production (docker-compose sets this); SQLite fallback for
    # lightweight local development and CI unit tests.
    database_url: str = "sqlite:///./fraudshield_dev.db"

    # Auth
    secret_key: str = "dev-only-secret-change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    # ML artifact storage
    ml_artifact_dir: str = "ml_artifacts"

    # Risk scoring weights (rule vs model blend)
    risk_rule_weight: float = 0.5
    risk_supervised_weight: float = 0.35
    risk_anomaly_weight: float = 0.15

    class Config:
        env_file = ".env"
        env_prefix = "FRAUDSHIELD_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
