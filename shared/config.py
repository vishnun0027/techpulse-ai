from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-8b-instant", env="GROQ_MODEL")

    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")
    upstash_redis_rest_url: str = Field(..., env="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(..., env="UPSTASH_REDIS_REST_TOKEN")
    slack_webhook_url: str = Field("", env="SLACK_WEBHOOK_URL")
    discord_webhook_url: str = Field("", env="DISCORD_WEBHOOK_URL")
    top_n_articles: int = Field(10, env="TOP_N_ARTICLES")
    dedup_ttl_days: int = Field(7, env="DEDUP_TTL_DAYS")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()