import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


print("---- ENV VARS RELEVANT TO PYDANTIC SETTINGS (config.py) ----")
relevant_vars = ["DATABASE_URL", "OPENAI_API_KEY", "LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY"]
for var_name in relevant_vars:
    value = os.getenv(var_name)
    print(f"{var_name} (from os.getenv): {value}")
print("--------------------------------------------------------")

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    LANGCHAIN_TRACING_V2: str = False
    LANGCHAIN_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding='utf-8', extra='ignore')

settings = Settings()

# Optional: Print what Pydantic loaded
print(f"Pydantic loaded DATABASE_URL: {settings.DATABASE_URL}")
print(f"Pydantic loaded OPENAI_API_KEY: {settings.OPENAI_API_KEY}")