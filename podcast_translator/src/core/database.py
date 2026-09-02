from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import settings

engine = create_async_engine(
    str(settings.PCT_DATABASE_URL), 
    pool_size=settings.PCT_DATABASE_POOL_SIZE,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

async def get_db_session():
    """FastAPI 依赖注入使用的数据库 Session"""
    async with AsyncSessionLocal() as session:
        yield session
