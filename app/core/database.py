from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,  #True, если надо видеть SQL-запросы в консоли (пока не нужно, но на всякий случай)
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """Зависимость FastAPI для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        yield session
