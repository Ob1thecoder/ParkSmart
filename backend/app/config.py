from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    tfnsw_api_key: str = ""
    openai_api_key: str = ""
    db_path: Path = Path("parksmart.db")
    database_url: Optional[str] = None  # PostgreSQL connection string for production
    fixtures_dir: Path = Path("data_raw/tfnsw_fixtures")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def use_postgres(self) -> bool:
        return self.database_url is not None


settings = Settings()


def get_settings() -> Settings:
    return settings
