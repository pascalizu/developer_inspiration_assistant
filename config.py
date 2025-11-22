# config.py
from pydantic_settings import BaseSettings
from omegaconf import OmegaConf
from pathlib import Path

class Settings(BaseSettings):
    groq_api_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()

# Load YAML config
config = OmegaConf.load(Path(__file__).parent / "config.yaml")