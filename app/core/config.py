from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

def find_base_dir():
    """
    Ищем файл .env, начиная с корня проекта.
    По какой-то причине он у меня не читался, поэтому пришлось так сделать
    """
    current = Path(__file__).resolve()
    for _ in range(5):
        current = current.parent
        if (current / ".env").exists():
            return current
    return Path(__file__).resolve().parent.parent.parent

BASE_DIR = find_base_dir()
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    # База данных: по умолчанию SQLite. С postgres пока лень разбираться, для одноразовых тестов норм
    DATABASE_URL: str = "sqlite+aiosqlite:///./university.db"

    # Postgres, оставила на потом, когда +- разберусь с функциями
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    # Безопасность JWT
    SECRET_KEY: str = "dev_secret_key_12345_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Демо-режим для тестов, чтобы отдельно проверять для себя их работоспособность
    DEMO_MODE: bool = True

    # Настройки Pydantic v2. Пока оставлю, мб потом уберу, пока не уверена
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    @property
    def database_url(self) -> str:
        """Возвращает актуальный URL базы данных"""
        # Если задан DATABASE_URL явно и он не дефолтный — используем его
        if self.DATABASE_URL and self.DATABASE_URL != "sqlite+aiosqlite:///./university.db":
            return self.DATABASE_URL
        # Если заданы данные Postgres — собираем URL
        if self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        # Иначе — SQLite
        return self.DATABASE_URL

settings = Settings()
