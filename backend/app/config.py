from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://fasikul:password@postgres:5432/fasikul"

    # Redis
    redis_url: str = "redis://:password@redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "fasikul"
    minio_secret_key: str = "password"
    minio_bucket: str = "fasikul"
    minio_secure: bool = False

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "source_chunks"
    embedding_dim: int = 768

    # LLM Providers
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    anthropic_api_key: str = ""

    # LLM routing: which pass uses which provider
    llm_topic_extraction: Literal["deepseek", "groq", "anthropic"] = "deepseek"
    llm_pass1_outline: Literal["deepseek", "groq", "anthropic"] = "deepseek"
    llm_pass2_expand: Literal["deepseek", "groq", "anthropic"] = "deepseek"
    llm_pass3_enrich: Literal["deepseek", "groq", "anthropic"] = "deepseek"
    llm_pass4_questions: Literal["deepseek", "groq", "anthropic"] = "deepseek"
    llm_pass5_qa: Literal["deepseek", "groq", "anthropic"] = "groq"

    # App
    default_language: str = "tr"
    default_depth: str = "comprehensive"
    secret_key: str = "change_me"
    domain: str = "localhost"


settings = Settings()
