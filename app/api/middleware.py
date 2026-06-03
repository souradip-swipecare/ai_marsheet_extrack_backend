"""
Centralized middleware module for the application
Follows MVC architecture - all middleware logic in one place
"""
from typing import Optional, Dict, Any
from fastapi import Request
from jose import JWTError, jwt
from loguru import logger

from app.core.config import settings


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT token
    Returns user data if valid, None if invalid
    
    Args:
        token: JWT token string
        
    Returns:
        Dict with user_id, email, role if valid
        None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check token type
        if payload.get("type") != "access":
            logger.debug("Invalid token type")
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
            logger.debug("Token missing subject")
            return None
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role", "user")
        }
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected JWT error: {e}")
        return None


async def jwt_auth_middleware(request: Request) -> None:
    """
    JWT Authentication Middleware
    
    Extracts JWT token from Authorization header,
    validates it, and adds user info to request.state.user
    
    This is OPTIONAL authentication - requests are not blocked
    if token is missing or invalid. The request.state.user will
    be None for unauthenticated requests.
    
    Usage in routes:
        current_user = getattr(request.state, "user", None)
        if current_user:
            user_id = current_user["user_id"]
            # Log to MongoDB, track usage, etc.
    
    Args:
        request: FastAPI Request object
    """
    # Initialize user as None (unauthenticated by default)
    request.state.user = None
    
    # Skip auth check if MongoDB not enabled
    if not settings.mongodb_enabled:
        return
    
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.debug("No Authorization header found")
        return
    
    # Parse Bearer token
    parts = auth_header.split()
    if len(parts) != 2:
        logger.debug("Invalid Authorization header format")
        return
    
    if parts[0].lower() != "bearer":
        logger.debug("Authorization header is not Bearer type")
        return
    
    token = parts[1]
    
    # Decode and validate token
    user_data = decode_jwt_token(token)
    if user_data:
        request.state.user = user_data
        logger.debug(f"Authenticated user: {user_data['email']}")
    else:
        logger.debug("Invalid or expired token")


async def log_user_activity_middleware(request: Request) -> None:
    """
    Log user activity to MongoDB if user is authenticated
    
    This runs AFTER jwt_auth_middleware has populated request.state.user
    
    Args:
        request: FastAPI Request object
    """
    # Skip if MongoDB not enabled
    if not settings.mongodb_enabled:
        return
    
    # Skip if user not authenticated
    current_user = getattr(request.state, "user", None)
    if not current_user:
        return
    
    # Only log for API endpoints, not static files or docs
    if not request.url.path.startswith("/api/v1/"):
        return
    
    # Import here to avoid circular imports
    try:
        from app.services.logging_service import logging_service
        from app.models.user_schemas import UserActivityLog
        from bson import ObjectId
        from datetime import datetime
        
        # Determine action from path
        action = "api_call"
        if "extract" in request.url.path:
            action = "extract"
        elif "batch" in request.url.path:
            action = "batch_extract"
        elif "job" in request.url.path:
            action = "job_check"
        
        # Log activity
        await logging_service.log_user_activity(UserActivityLog(
            user_id=ObjectId(current_user["user_id"]),
            action=action,
            details={
                "path": request.url.path,
                "method": request.method
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            timestamp=datetime.utcnow()
        ))
    except Exception as e:
        # Don't fail the request if logging fails
        logger.error(f"Failed to log user activity: {e}")


# Middleware initialization order (registered in main.py)
MIDDLEWARE_ORDER = """
Middleware execution order (outer to inner):

1. CORS Middleware (FastAPI built-in)
   ↓
2. GZip Compression (FastAPI built-in)
   ↓
3. Security Headers Middleware
   ↓
4. Request ID Middleware
   ↓
5. JWT Authentication Middleware ← Extract & validate JWT
   ↓
6. Route Handler (Controllers)
   ↓
7. Response

Note: Middleware runs in reverse order on response
(inner to outer)
"""
