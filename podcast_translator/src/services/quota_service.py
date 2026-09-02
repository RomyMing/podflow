import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.user_repo import UserRepository
from src.models.user import User
from src.schemas.user import QuotaResponse
from src.core.exceptions import QuotaExceededError, ResourceNotFoundError

class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(User, db)

    async def check_quota(self, user_id: uuid.UUID) -> bool:
        user = await self.user_repo.get(user_id)
        if not user:
            raise ResourceNotFoundError("User not found")
            
        return user.monthly_used < user.monthly_quota

    async def consume_quota(self, user_id: uuid.UUID, amount: int = 1) -> None:
        user = await self.user_repo.get(user_id)
        if not user:
            raise ResourceNotFoundError("User not found")
            
        if user.monthly_used + amount > user.monthly_quota:
            raise QuotaExceededError("本月可用额度不足，请联系管理员增加额度或等待下次重置。")
            
        await self.user_repo.update(user, {"monthly_used": user.monthly_used + amount})
        await self.db.commit()

    async def refund_quota(self, user_id: uuid.UUID, amount: int = 1) -> None:
        """BUG-04 修复：配额补偿回滚 - 当下游操作（如 S3 上传）失败时归还已扣配额"""
        user = await self.user_repo.get(user_id)
        if not user:
            raise ResourceNotFoundError("User not found")
        
        new_used = max(0, user.monthly_used - amount)
        await self.user_repo.update(user, {"monthly_used": new_used})
        await self.db.commit()

    async def get_quota_info(self, user_id: uuid.UUID) -> QuotaResponse:
        user = await self.user_repo.get(user_id)
        if not user:
            raise ResourceNotFoundError("User not found")
            
        remaining = max(0, user.monthly_quota - user.monthly_used)
        return QuotaResponse(
            total=user.monthly_quota,
            used=user.monthly_used,
            remaining=remaining,
            reset_at=user.quota_reset_at
        )
