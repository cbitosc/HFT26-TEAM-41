from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    recruiter_api_key: str = ""
    """Required in the X-Recruiter-Key header of recruiter routes; unset: they return 503."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
