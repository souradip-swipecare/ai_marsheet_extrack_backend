"""
Authentication routes - register, login, token refresh
"""
from fastapi import APIRouter, HTTPException, status, Depends
from loguru import logger

from app.models.user_schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user_from_token,
    decode_token
)
from app.services.user_service import user_service
from app.services.logging_service import logging_service
from datetime import timedelta
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        user_doc = await user_service.create_user(user_data)
        
        return UserResponse(
            user_id=str(user_doc["_id"]),
            email=user_doc["email"],
            full_name=user_doc["full_name"],
            organization=user_doc.get("organization"),
            role=user_doc["role"],
            api_key=user_doc["api_key"],
            is_active=user_doc["is_active"],
            created_at=user_doc["created_at"],
            total_extractions=user_doc.get("total_extractions", 0)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password"""
    user = await user_service.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(
        data={
            "sub": str(user["_id"]),
            "email": user["email"],
            "role": user["role"]
        }
    )
    
    refresh_token = create_refresh_token(
        data={
            "sub": str(user["_id"]),
            "email": user["email"]
        }
    )
    
    # Log activity
    await logging_service.log_user_activity({
        "user_id": str(user["_id"]),
        "action": "login",
        "details": {"email": user["email"]}
    })
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        payload = decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        # Verify user still exists and is active
        user = await user_service.get_user_by_id(user_id)
        if not user or not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token = create_access_token(
            data={
                "sub": user_id,
                "email": email,
                "role": user["role"]
            }
        )
        
        # Create new refresh token
        new_refresh_token = create_refresh_token(
            data={
                "sub": user_id,
                "email": email
            }
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: dict = Depends(get_current_user_from_token)):
    """Get current authenticated user"""
    user = await user_service.get_user_by_id(current_user["user_id"])
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        user_id=str(user["_id"]),
        email=user["email"],
        full_name=user["full_name"],
        organization=user.get("organization"),
        role=user["role"],
        api_key=user["api_key"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        total_extractions=user.get("total_extractions", 0)
    )


@router.get("/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user_from_token)):
    """Get current user's usage statistics"""
    stats = await logging_service.get_user_stats(current_user["user_id"])
    logs = await logging_service.get_user_extraction_logs(current_user["user_id"], limit=10)
    
    return {
        "user_id": current_user["user_id"],
        "statistics": stats,
        "recent_extractions": logs
    }
