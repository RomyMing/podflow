from typing import Optional
from sqlalchemy import select
from src.repositories.base import BaseRepository
from src.models.user import User

class UserRepository(BaseRepository[User]):
    """
    User 数据访问仓库
    """

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_wechat_openid(self, openid: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.wechat_openid == openid))
        return result.scalar_one_or_none()
