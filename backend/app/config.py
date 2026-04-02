from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # openai | gemini (default gemini for this project when GOOGLE_API_KEY is set)
    llm_provider: str = "gemini"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    google_api_key: str | None = None
    # 1.5-* removed from API; 2.5-flash-lite is budget-friendly (see ai.google.dev/gemini-api/docs/models/gemini).
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    serpapi_api_key: str | None = None
    # One LLM call, no Chroma/RAG embeddings — best for free-tier / low quota (SIMPLE_MODE=true).
    simple_mode: bool = False
    demo_mode: bool = False
    redis_url: str = "redis://localhost:6379/0"
    chroma_host: str = "localhost"
    chroma_port: int = 8000


settings = Settings()
