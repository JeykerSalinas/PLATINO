from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Platino Backend"
    database_url: str = "sqlite:///./platino.db"

    class Config:
        env_file = ".env"

settings = Settings()
