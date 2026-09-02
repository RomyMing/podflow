from fastapi import APIRouter, Depends, HTTPException, status

from src.core.exceptions import AuthenticationError, FeatureDisabledError
from src.dependencies import get_auth_service
from src.schemas.auth import RefreshRequest, SendSMSRequest, SMSLoginRequest, TokenResponse, WechatLoginRequest
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sms/send", status_code=status.HTTP_200_OK)
async def send_sms_code(
    request: SendSMSRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        success = await auth_service.send_sms_code(request.phone)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send SMS code")
        return {"message": "Code sent successfully"}
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/sms/login", response_model=TokenResponse)
async def login_with_sms(
    request: SMSLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await auth_service.login_with_sms(request.phone, request.code)
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/demo/login", response_model=TokenResponse)
async def login_demo(
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await auth_service.login_demo()
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/wechat/login", response_model=TokenResponse)
async def login_with_wechat(
    request: WechatLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await auth_service.login_with_wechat(request.code)
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await auth_service.refresh_token(request.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
