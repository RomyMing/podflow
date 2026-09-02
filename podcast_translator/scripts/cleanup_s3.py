import asyncio

from src.core.database import AsyncSessionLocal
from src.services.artifact_cleanup_service import ArtifactCleanupService


async def main() -> None:
    async with AsyncSessionLocal() as session:
        deleted = await ArtifactCleanupService(session).cleanup_completed_tasks()
        print(f"Deleted {deleted} intermediate object(s).")


if __name__ == "__main__":
    asyncio.run(main())
