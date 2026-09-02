from fastapi import APIRouter, Depends, HTTPException, status
from src.schemas.user import (
    ApiKeyProvider,
    QuotaResponse,
    UserApiKeyResponse,
    UserApiKeyUpdateRequest,
    UserResponse,
)
from src.models.user import User
from src.services.quota_service import QuotaService
from src.dependencies import get_current_user, get_quota_service
from src.core.database import get_db_session
from src.services.user_api_key_service import UserApiKeyService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me/quota", response_model=QuotaResponse)
async def get_my_quota(
    current_user: User = Depends(get_current_user),
    quota_service: QuotaService = Depends(get_quota_service)
):
    return await quota_service.get_quota_info(current_user.id)


@router.get("/me/api-keys", response_model=list[UserApiKeyResponse])
async def list_my_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await UserApiKeyService(db).list_api_keys(current_user.id)


@router.get("/me/api-keys/{provider}", response_model=UserApiKeyResponse)
async def get_my_api_key(
    provider: ApiKeyProvider,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    record = await UserApiKeyService(db).get_api_key(current_user.id, provider)
    if record is None:
        raise HTTPException(status_code=404, detail="API key is not configured")
    return record


@router.put("/me/api-keys/{provider}", response_model=UserApiKeyResponse)
async def upsert_my_api_key(
    provider: ApiKeyProvider,
    request: UserApiKeyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await UserApiKeyService(db).upsert_api_key(
            current_user.id,
            provider,
            api_key=request.api_key,
            base_url=request.base_url,
            region=request.region,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/me/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_api_key(
    provider: ApiKeyProvider,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    await UserApiKeyService(db).delete_api_key(current_user.id, provider)


@router.post("/me/api-keys/{provider}/verify", response_model=UserApiKeyResponse)
async def verify_my_api_key(
    provider: ApiKeyProvider,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await UserApiKeyService(db).verify_api_key(current_user.id, provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
