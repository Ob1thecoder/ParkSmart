from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    tfnsw_api_key: str = ""
    anthropic_api_key: str = ""
    db_path: Path = Path("parksmart.db")
    fixtures_dir: Path = Path("data_raw/tfnsw_fixtures")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def get_settings() -> Settings:
    return settings
