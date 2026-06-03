from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # first load varriable from env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    app_name: str = Field(default="Marksheet Extraction API")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    google_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    default_llm_provider: str = Field(default="gemini")

    gemini_model: str = Field(default="gemini-2.5-flash")
    openai_model: str = Field(default="gpt-4o")
    
    api_key_enabled: bool = Field(default=False)
    api_key: Optional[str] = Field(default=None)
    
    max_file_size_mb: int = Field(default=10)
    allowed_extensions: str = Field(default="jpg,jpeg,png,pdf,webp")
    
    rate_limit_requests: int = Field(default=100)
    rate_limit_window_seconds: int = Field(default=60)
    
    
    save_ocr_text: bool = Field(default=True)
    ocr_extract_dir: str = Field(default="extract")
    ocr_confidence_threshold: float = Field(default=0.60)
    ocr_use_parallel: bool = Field(default=False)  # Set to False if ThreadPoolExecutor not supported
    
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/app.log")
    
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_enabled: bool = Field(default=False)
    
    # MongoDB Settings
    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_db_name: str = Field(default="marksheet_extraction")
    mongodb_enabled: bool = Field(default=False)
    
    # JWT Authentication
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]
    
    def validate_llm_config(self) -> bool:
        if self.default_llm_provider == "gemini" and not self.google_api_key:
            return False
        if self.default_llm_provider == "openai" and not self.openai_api_key:
            return False
        return True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Global settings instance
settings = get_settings()
