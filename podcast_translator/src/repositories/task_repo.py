import uuid
from typing import List
from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import selectinload
from src.repositories.base import BaseRepository
from src.models.task import Task
from src.models.segment import Segment

# In-flight statuses that count against the per-user active-task limit.
ACTIVE_TASK_STATUSES = ("pending", "processing")

class TaskRepository(BaseRepository[Task]):
    """
    Task Data Access Repository
    """
    async def get_user_tasks(self, user_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(desc(Task.created_at))
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_task_segments(
        self, task_id: uuid.UUID, skip: int = 0, limit: int = 200
    ) -> List[Segment]:
        result = await self.session.execute(
            select(Segment)
            .where(Segment.task_id == task_id)
            .options(selectinload(Segment.speaker))
            .order_by(asc(Segment.start_time))
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count_active_tasks(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.user_id == user_id, Task.status.in_(ACTIVE_TASK_STATUSES))
        )
        return int(result.scalar_one())

    async def get_stall_candidates(self, before: datetime, limit: int) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.status == "processing", Task.last_activity_at <= before)
            .order_by(asc(Task.last_activity_at))
            .limit(limit)
        )
        return list(result.scalars().all())
