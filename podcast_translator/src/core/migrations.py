import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from src.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", str(settings.PCT_DATABASE_URL))
    return config


def run_startup_migrations() -> None:
    logger.info("Running database migrations to head")
    command.upgrade(build_alembic_config(), "head")

