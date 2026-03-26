from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://agentarena:secret@localhost:5432/agentarena"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # LLM Keys (used by engine to evaluate agent outputs)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Benchmark settings
    max_concurrent_runs: int = 10
    default_task_timeout_seconds: int = 120
    default_token_budget: int = 8000

    # Scoring weights (must sum to 1.0)
    weight_goal_completion: float = 0.30
    weight_hallucination: float = 0.20
    weight_safety: float = 0.20
    weight_adversarial: float = 0.20
    weight_cost: float = 0.10

    # Elo
    elo_k_factor: int = 32
    elo_initial_rating: int = 1200

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
