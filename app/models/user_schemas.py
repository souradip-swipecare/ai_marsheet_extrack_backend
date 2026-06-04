"""
User and authentication related schemas
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=2)
    organization: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    organization: Optional[str] = None
    role: str = "user"
    api_key: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    total_extractions: int = 0
    
    class Config:
        from_attributes = True


class ExtractionLogCreate(BaseModel):
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    filename: str
    file_size_bytes: int
    extraction_method: str
    status: str = "processing"
    request_id: str


class ExtractionLogUpdate(BaseModel):
    job_id: Optional[str] = None
    status: Optional[str] = None
    extraction_method: Optional[str] = None
    extraction_data: Optional[dict] = None
    extraction_confidence: Optional[float] = None
    processing_time_ms: Optional[float] = None
    error: Optional[str] = None
    cost_estimate_usd: Optional[float] = None


class UserActivityLog(BaseModel):
    user_id: str
    action: str  # "login", "logout", "extract", "batch_extract", etc.
    details: dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class APIUsageStats(BaseModel):
    user_id: str
    date: str  # YYYY-MM-DD
    total_requests: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    total_cost_usd: float = 0.0
    total_processing_time_ms: float = 0.0
