from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import settings
from src.core.migrations import (
    PROJECT_ROOT,
    build_alembic_config,
    run_startup_migrations,
)
from src.main import lifespan


def test_build_alembic_config_points_to_repo_files():
    config = build_alembic_config()

    assert Path(config.config_file_name) == PROJECT_ROOT / "alembic.ini"
    assert Path(config.get_main_option("script_location")) == PROJECT_ROOT / "migrations"
    assert config.get_main_option("sqlalchemy.url") == str(settings.PCT_DATABASE_URL)


def test_run_startup_migrations_upgrades_to_head():
    fake_config = MagicMock()

    with (
        patch(
            "src.core.migrations.build_alembic_config",
            return_value=fake_config,
        ) as mock_build,
        patch("src.core.migrations.command.upgrade") as mock_upgrade,
    ):
        run_startup_migrations()

    mock_build.assert_called_once_with()
    mock_upgrade.assert_called_once_with(fake_config, "head")


@pytest.mark.asyncio
async def test_lifespan_runs_migrations_when_enabled():
    with (
        patch.object(settings, "PCT_AUTO_MIGRATE_ON_STARTUP", True),
        patch("src.main.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        async with lifespan(MagicMock()):
            pass

    mock_to_thread.assert_awaited_once_with(run_startup_migrations)


@pytest.mark.asyncio
async def test_lifespan_skips_migrations_when_disabled():
    with (
        patch.object(settings, "PCT_AUTO_MIGRATE_ON_STARTUP", False),
        patch("src.main.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        async with lifespan(MagicMock()):
            pass

    mock_to_thread.assert_not_awaited()
