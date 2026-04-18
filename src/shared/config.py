from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"

    supabase_url: str
    supabase_key: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    top_n_articles: int = 10
    dedup_ttl_days: int = 7
    collection_interval_days: int = 14


settings = Settings()