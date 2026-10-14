# Configurations for the API like secrets and variable values

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Config(BaseSettings):
  gemini_api_key: SecretStr
  model_config = SettingsConfigDict(
    env_file = ".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore"
  )
  
settings = Config()
