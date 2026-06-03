
from typing import Optional, Dict, Any
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader, APIKeyQuery
from jose import JWTError, jwt
from loguru import logger

from app.core.config import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


async def get_api_key(
    api_key_header: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Security(api_key_query)
) -> Optional[str]:

    if not settings.api_key_enabled:
        return None
    
    provided_key = api_key_header or api_key_query
    
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Provide it via X-API-Key header or api_key query parameter.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    if provided_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return provided_key


async def optional_api_key(
    api_key_header: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Security(api_key_query)
) -> Optional[str]:
    """Optional API key - doesn't raise error if missing"""
    return api_key_header or api_key_query


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT token
    Returns user data if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check token type
        if payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
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
    Middleware to extract and validate JWT token from request
    Adds user info to request.state.user if token is valid
    Does not block request if token is missing/invalid (optional auth)
    """
    # Initialize user as None
    request.state.user = None
    
    # Skip auth check if MongoDB not enabled
    if not settings.mongodb_enabled:
        return
    
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return
    
    # Parse Bearer token
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return
    
    token = parts[1]
    
    # Decode and validate token
    user_data = decode_jwt_token(token)
    if user_data:
        request.state.user = user_data
        logger.debug(f"Authenticated user: {user_data['user_id']}")
