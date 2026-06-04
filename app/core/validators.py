
from typing import Optional, Dict, Any
from loguru import logger

from app.core.config import settings


class ConfigValidator:
    
    @staticmethod
    def validate_llm_config() -> tuple[bool, Optional[str]]:
     
        provider = settings.default_llm_provider.lower()
        
        if provider == "gemini":
            if not settings.google_api_key:
                return False, "gapikey is required when defaultllm=gemini"
            
            # Validate model name format (2026 models)
            valid_models = [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-3.5-flash",
                "gemini-flash-latest",
                "gemini-pro-latest"
            ]
            
            if settings.gemini_model not in valid_models:
                return False, (
                    f"Invalid Gemini model: {settings.gemini_model}. "
                    f"Valid options: {', '.join(valid_models)}"
                )
                
        elif provider == "openai":
            if not settings.openai_api_key:
                return False, "OPENAI_API_KEY is required when DEFAULT_LLM_PROVIDER=openai"
            
            valid_models = ["gpt-4o", "gpt-4-turbo", "gpt-4-vision-preview"]
            if settings.openai_model not in valid_models:
                return False, (
                    f"Invalid OpenAI model: {settings.openai_model}. "
                    f"Valid options: {', '.join(valid_models)}"
                )
        else:
            return False, f"Invalid LLM provider: {provider}. Must be 'gemini' or 'openai'"
        
        return True, None
    
    @staticmethod
    def validate_redis_config() -> tuple[bool, Optional[str]]:
        if not settings.celery_enabled:
            return True, None
        
        redis_url = settings.get_redis_url()
        
        if not redis_url or redis_url == "redis://localhost:6379/0":
            logger.warning("Using default local Redis configuration")
            return True, None
        
        # Validate Redis URL format
        if not redis_url.startswith("redis://"):
            return False, f"Invalid Redis URL format: {redis_url}"
        
        # Check if address is configured
        if not settings.redis_addr:
            return False, "REDIS_ADDR is required when CELERY_ENABLED=true"
        
        return True, None
    
    @staticmethod
    def validate_mongodb_config() -> tuple[bool, Optional[str]]:
        """
        Validate MongoDB configuration.
        
        Returns:
            (is_valid, error_message)
        """
        if not settings.mongodb_enabled:
            return True, None
        
        if not settings.mongodb_url:
            return False, "MONGODB_URL is required when MONGODB_ENABLED=true"
        
        if not settings.mongodb_db_name:
            return False, "MONGODB_DB_NAME is required when MONGODB_ENABLED=true"
        
        return True, None
    
    @staticmethod
    def validate_all() -> Dict[str, Any]:
        """
        Validate all configuration settings.
        
        Returns:
            dict: Validation results with errors
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Validate LLM
        llm_valid, llm_error = ConfigValidator.validate_llm_config()
        if not llm_valid:
            results["valid"] = False
            results["errors"].append(f"LLM Config: {llm_error}")
        
        # Validate Redis
        redis_valid, redis_error = ConfigValidator.validate_redis_config()
        if not redis_valid:
            results["valid"] = False
            results["errors"].append(f"Redis Config: {redis_error}")
        elif redis_error:
            results["warnings"].append(f"Redis: {redis_error}")
        
        # Validate MongoDB
        mongo_valid, mongo_error = ConfigValidator.validate_mongodb_config()
        if not mongo_valid:
            results["warnings"].append(f"MongoDB Config: {mongo_error}")
        
        # Validate file settings
        if settings.max_file_size_mb <= 0 or settings.max_file_size_mb > 100:
            results["warnings"].append(
                f"MAX_FILE_SIZE_MB={settings.max_file_size_mb} is unusual (recommended: 5-20 MB)"
            )
        
        if settings.ocr_confidence_threshold < 0.5 or settings.ocr_confidence_threshold > 0.95:
            results["warnings"].append(
                f"OCR_CONFIDENCE_THRESHOLD={settings.ocr_confidence_threshold} "
                f"is unusual (recommended: 0.60-0.80)"
            )
        
        return results


class RuntimeValidator:
    
    @staticmethod
    def validate_extraction_result(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
       
        if not isinstance(data, dict):
            return False, "Extraction result must be a dictionary"
        
        candidate = data.get("candidate")
        if not candidate:
            return False, "Missing candidate information"
        
        if not isinstance(candidate, dict):
            return False, "Candidate must be a dictionary"
        
        if not candidate.get("name"):
            return False, "Missing candidate name"
        
        if not candidate.get("roll_number"):
            return False, "Missing roll number"
        
        examination = data.get("examination")
        if not examination or not isinstance(examination, dict):
            return False, "Missing or invalid examination details"
        
        subjects = data.get("subjects")
        if not subjects:
            return False, "No subjects found in extraction"
        
        if not isinstance(subjects, list) or len(subjects) == 0:
            return False, "Subjects must be a non-empty list"
        
        return True, None


def log_validation_results(results: Dict[str, Any]) -> None:
    if results["valid"]:
        logger.success("✓ Configuration validation passed")
    else:
        logger.error("✗ Configuration validation failed")
        for error in results["errors"]:
            logger.error(f"  - {error}")
    
    if results["warnings"]:
        logger.warning(f"Configuration warnings ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            logger.warning(f"  - {warning}")
