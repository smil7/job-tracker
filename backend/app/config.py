from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jobtracker:jobtracker@localhost:5433/jobtracker"
    test_database_url: str = "postgresql+asyncpg://jobtracker:jobtracker@localhost:5433/jobtracker_test"
    cors_origins: list[str] = ["http://localhost:5173"]
    openrouter_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-sonnet-5.5"

    # "development" or "production". Production refuses to start with login turned off.
    environment: str = "development"
    git_sha: str = "dev"

    # Login. When auth_disabled is true, every request runs as one fixed dev user.
    # The default is false, so a missing setting never leaves the API open.
    auth_disabled: bool = False
    cognito_region: str = ""
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    # Hosted UI domain. Used once per new user to read their email from Cognito.
    cognito_domain: str = ""

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"

    def check_auth_config(self) -> None:
        """Stop the app at start-up if login is set up in an unsafe or incomplete way."""
        if self.auth_disabled:
            if self.environment == "production":
                raise RuntimeError("AUTH_DISABLED=true is not allowed when ENVIRONMENT=production")
            return
        missing = [
            name
            for name in ("cognito_region", "cognito_user_pool_id", "cognito_app_client_id")
            if not getattr(self, name)
        ]
        if missing:
            raise RuntimeError(
                "Login is on, but these settings are empty: "
                + ", ".join(m.upper() for m in missing)
                + ". Set them, or set AUTH_DISABLED=true for local development."
            )


settings = Settings()
