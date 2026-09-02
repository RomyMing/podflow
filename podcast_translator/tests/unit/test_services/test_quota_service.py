"""
QuotaService 单元测试
"""
import uuid
import pytest

from src.services.quota_service import QuotaService
from src.schemas.user import QuotaResponse
from src.core.exceptions import QuotaExceededError, ResourceNotFoundError


class TestCheckQuota:
    async def test_has_remaining_quota(self, db_session, mock_user):
        service = QuotaService(db_session)
        result = await service.check_quota(mock_user.id)
        assert result is True

    async def test_quota_exhausted(self, db_session, mock_user_exhausted):
        service = QuotaService(db_session)
        result = await service.check_quota(mock_user_exhausted.id)
        assert result is False

    async def test_check_quota_nonexistent_user(self, db_session):
        service = QuotaService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await service.check_quota(uuid.uuid4())


class TestConsumeQuota:
    async def test_consume_quota_success(self, db_session, mock_user):
        service = QuotaService(db_session)
        original_used = mock_user.monthly_used
        await service.consume_quota(mock_user.id)
        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == original_used + 1

    async def test_consume_quota_insufficient(self, db_session, mock_user_exhausted):
        service = QuotaService(db_session)
        with pytest.raises(QuotaExceededError):
            await service.consume_quota(mock_user_exhausted.id)


class TestRefundQuota:
    async def test_refund_quota(self, db_session, mock_user):
        """消费后退还 → used 恢复"""
        service = QuotaService(db_session)
        await service.consume_quota(mock_user.id)
        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 1

        await service.refund_quota(mock_user.id)
        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0

    async def test_refund_quota_floor_zero(self, db_session, mock_user):
        """退还不会低于 0"""
        service = QuotaService(db_session)
        await service.refund_quota(mock_user.id)
        await db_session.refresh(mock_user)
        assert mock_user.monthly_used == 0


class TestGetQuotaInfo:
    async def test_get_quota_info(self, db_session, mock_user):
        service = QuotaService(db_session)
        result = await service.get_quota_info(mock_user.id)
        assert isinstance(result, QuotaResponse)
        assert result.total == 5
        assert result.used == 0
        assert result.remaining == 5

    async def test_get_quota_info_nonexistent(self, db_session):
        service = QuotaService(db_session)
        with pytest.raises(ResourceNotFoundError):
            await service.get_quota_info(uuid.uuid4())
