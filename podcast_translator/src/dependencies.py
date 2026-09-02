import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.services.auth_service import AuthService
from src.services.quota_service import QuotaService
from src.core.security import decode_token
from src.repositories.user_repo import UserRepository
from src.models.user import User

from src.services.storage_service import StorageService
from src.services.task_service import TaskService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_auth_service(db: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(db)

def get_quota_service(db: AsyncSession = Depends(get_db_session)) -> QuotaService:
    return QuotaService(db)

def get_storage_service() -> StorageService:
    return StorageService()

def get_task_service(db: AsyncSession = Depends(get_db_session)) -> TaskService:
    return TaskService(db)

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        if payload.get("token_type") != "access":
            raise credentials_exception
            
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise credentials_exception
        
    user_repo = UserRepository(User, db)
    user = await user_repo.get(user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user
