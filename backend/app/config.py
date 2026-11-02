from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jobtracker:jobtracker@localhost:5433/jobtracker"
    test_database_url: str = "postgresql+asyncpg://jobtracker:jobtracker@localhost:5433/jobtracker_test"
    cors_origins: list[str] = ["http://localhost:5173"]
    openrouter_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-sonnet-5.5"


settings = Settings()
