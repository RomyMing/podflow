"""
PodFlow 测试全局 Fixtures

使用 PostgreSQL 测试数据库 (端口 5433, docker-compose 中 postgres_test 服务)
每个测试函数独立初始化 schema，使用嵌套事务 (SAVEPOINT) 隔离并自动回滚。
"""
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

# ────────────────────────────────────────────────────────────────────
# 测试数据库 URL — 指向 docker-compose 中 postgres_test (端口 5433)
# ────────────────────────────────────────────────────────────────────
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres_password@localhost:5433/podcast_translator_test"


# ────────────────────────────────────────────────────────────────────
# 测试引擎 & Schema 初始化 (function scope 避免事件循环冲突)
# ────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_engine():
    """创建测试数据库引擎，每个测试函数独立建表和清理"""
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    from src.models.base import Base
    # 导入所有 model 以确保它们被注册到 metadata
    import src.models.task  # noqa: F401
    import src.models.user  # noqa: F401
    import src.models.speaker  # noqa: F401
    import src.models.segment  # noqa: F401
    import src.models.task_stage_run  # noqa: F401
    import src.models.user_api_key  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ────────────────────────────────────────────────────────────────────
# 测试 Session (函数级隔离 — 嵌套事务 SAVEPOINT 模式)
#
# 工作原理:
#   1. 获取一个真实的数据库连接
#   2. 开启一个连接级事务 (BEGIN)
#   3. 将 session 绑定到该连接，session 中的 commit() 只提交到 SAVEPOINT
#   4. 测试结束后 rollback 连接级事务，所有变更被撤销
# ────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试函数获得独立的 DB session，使用嵌套事务自动隔离"""
    async with test_engine.connect() as conn:
        # 开启外层连接级事务
        trans = await conn.begin()

        # 创建绑定到该连接的 session
        session_factory = async_sessionmaker(
            bind=conn,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        session = session_factory()

        # 开启 SAVEPOINT — session 的 commit() 只会提交到这个 savepoint
        await conn.begin_nested()

        # 每次 session commit 后自动开启新的 SAVEPOINT
        from sqlalchemy import event

        @event.listens_for(session.sync_session, "after_transaction_end")
        def reopen_nested(session_sync, transaction):
            if conn.closed or conn.invalidated:
                return
            if not conn.in_nested_transaction():
                try:
                    conn.sync_connection.begin_nested()
                except Exception:
                    pass

        yield session

        # 清理
        await session.close()
        # 回滚连接级事务 — 所有 SAVEPOINT 内的变更全部撤销
        await trans.rollback()


# ────────────────────────────────────────────────────────────────────
# Mock User
# ────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def mock_user(db_session: AsyncSession):
    """创建一个测试用户并提交到数据库"""
    from src.models.user import User

    user = User(
        id=uuid.uuid4(),
        phone="13800138000",
        nickname="TestUser",
        is_active=True,
        monthly_quota=5,
        monthly_used=0,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def mock_user_exhausted(db_session: AsyncSession):
    """创建一个配额已耗尽的测试用户"""
    from src.models.user import User

    user = User(
        id=uuid.uuid4(),
        phone="13900139000",
        nickname="ExhaustedUser",
        is_active=True,
        monthly_quota=5,
        monthly_used=5,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


# ────────────────────────────────────────────────────────────────────
# Auth Tokens
# ────────────────────────────────────────────────────────────────────
@pytest.fixture
def auth_tokens(mock_user):
    """为 mock_user 生成有效的 JWT token pair"""
    from src.core.security import create_access_token, create_refresh_token

    data = {"sub": str(mock_user.id)}
    return {
        "access": create_access_token(data),
        "refresh": create_refresh_token(data),
    }


@pytest.fixture
def auth_headers(auth_tokens):
    """带有 Authorization header 的字典，方便传入 httpx client"""
    return {"Authorization": f"Bearer {auth_tokens['access']}"}


# ────────────────────────────────────────────────────────────────────
# FastAPI 测试客户端
# ────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession):
    """返回打过补丁的 FastAPI app 实例（注入测试 DB session）"""
    from src.main import app
    from src.core.database import get_db_session

    async def override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """无认证的 HTTP 测试客户端"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def authenticated_client(test_app, auth_headers) -> AsyncGenerator[AsyncClient, None]:
    """带 JWT 认证的 HTTP 测试客户端"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as c:
        yield c
