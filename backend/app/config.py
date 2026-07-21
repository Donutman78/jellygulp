from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jellyfin_url: str
    jellyfin_api_key: str
    database_url: str
    poll_interval_seconds: int = 10
    cors_origins: str = "*"

    model_config = SettingsConfigDict(case_sensitive=False)


settings = Settings()
