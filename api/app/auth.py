from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from .config import settings
from .database import db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


async def get_user_by_username(username: str):
    """Get user from database by username"""
    query = """
        SELECT id, username, email, hashed_password, is_active, is_admin, created_at
        FROM users
        WHERE username = $1
    """
    return await db.fetchrow(query, username)


async def get_user_by_id(user_id: int):
    """Get user from database by ID"""
    query = """
        SELECT id, username, email, is_active, is_admin, created_at
        FROM users
        WHERE id = $1
    """
    return await db.fetchrow(query, user_id)


async def authenticate_user(username: str, password: str):
    """Authenticate user with username and password"""
    user = await get_user_by_username(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get current user from JWT token"""
    if not credentials:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get current user if authenticated, otherwise None"""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def require_auth_if_needed(user=Depends(get_current_user_optional)):
    """Check authentication based on AUTH_MODE setting (deprecated, use specific functions)"""
    if settings.AUTH_MODE == "authenticated" and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


async def require_auth_for_submission(user=Depends(get_current_user_optional)):
    """Check if authentication is required for submissions"""
    if not settings.ALLOW_ANONYMOUS_SUBMISSIONS and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for submissions",
        )
    return user


async def require_auth_for_browsing(user=Depends(get_current_user_optional)):
    """Check if authentication is required for browsing/reading data"""
    if not settings.ALLOW_ANONYMOUS_BROWSING and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view data",
        )
    return user
