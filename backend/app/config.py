from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jellyfin_url: str
    jellyfin_api_key: str
    database_url: str
    poll_interval_seconds: int = 10
    cors_origins: str = "*"
    excluded_library_names: str = ""

    model_config = SettingsConfigDict(case_sensitive=False)

    @property
    def excluded_library_names_set(self) -> set[str]:
        return {
            name.strip().lower()
            for name in self.excluded_library_names.split(",")
            if name.strip()
        }


settings = Settings()
