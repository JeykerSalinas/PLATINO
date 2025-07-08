from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Platino Backend"
    # Por defecto asumimos que la base de datos se expone en localhost
    # cuando se levanta con `docker compose -f docker-compose.db.yml up -d`.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/platino"
    openai_api_key: str
    class Config:
        env_file = ".env"

settings = Settings()
