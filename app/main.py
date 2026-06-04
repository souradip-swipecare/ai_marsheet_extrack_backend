from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sys
import os
import time
import uuid

from app.core.config import settings
from app.core.validators import ConfigValidator, log_validation_results
from app.utils.exceptions import MarksheetExtractionError
from app.services.extraction import llm_service
from app.api.routes import api_router

limiter = Limiter(key_func=get_remote_address)

logger.remove()
if settings.debug:
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level
    )
else:
    logger.add(
        sys.stdout,
        format="{message}",
        level=settings.log_level,
        serialize=True
    )

os.makedirs("logs", exist_ok=True)
logger.add(
    settings.log_file,
    rotation="10 MB",
    retention="7 days",
    level=settings.log_level,
    serialize=not settings.debug
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # validate config
    validation_results = ConfigValidator.validate_all()
    log_validation_results(validation_results)
    
    if not validation_results["valid"]:
        logger.error("Application startup aborted due to configuration errors")
        raise RuntimeError("Invalid configuration - check logs for details")
    
    # Connect to MongoDB
    if settings.mongodb_enabled:
        from app.core.database import mongodb
        await mongodb.connect()
    
    # Initialize LLM service
    try:
        await llm_service.initialize()
        logger.success(f"✓ LLM service initialized ({settings.default_llm_provider} / {settings.gemini_model if settings.default_llm_provider == 'gemini' else settings.openai_model})")
    except Exception as e:
        logger.error(f"✗ LLM service initialization failed: {e}")
        raise RuntimeError(f"Failed to initialize LLM service: {e}")
    
    logger.success(f"✓ {settings.app_name} started successfully")
    yield
    
    # Shutdown - disconnect MongoDB
    if settings.mongodb_enabled:
        from app.core.database import mongodb
        await mongodb.disconnect()
    
    logger.info("Shutting down application")


# FastAPI application with production optimizations
app = FastAPI(
    title=settings.app_name,
    description="""ai powered marksheet data extract api
    """.format(version=settings.app_version),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    # OpenAPI/Swagger UI customization
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "showExtensions": True,
        "docExpansion": "none",
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
    },
    generate_unique_id_function=lambda route: f"{route.tags[0]}-{route.name}" if route.tags else route.name,
    # API metadata
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://aiintern.souradipproject.cloud",
            "description": "Production server"
        }
    ] if not settings.debug else [{"url": "http://localhost:8000", "description": "Development server"}],
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check and service status"
        },
        {
            "name": "Extraction",
            "description": "Marksheet data extraction endpoints (JWT authenticated)"
        },
        {
            "name": "Jobs",
            "description": "Async job management and status tracking"
        },
        {
            "name": "Batch",
            "description": "Batch processing for multiple files"
        },
        {
            "name": "Authentication",
            "description": "User registration, login, and token management"
        },
        {
            "name": "Schema",
            "description": "API schemas and documentation"
        }
    ]
)

# Security: Require JWT for all extraction endpoints
PROTECTED_PATHS = ["/api/v1/extract", "/api/v1/batch"]

@app.middleware("http")
async def enforce_jwt_on_extraction(request: Request, call_next):
    """
    Enforce JWT authentication on extraction endpoints
    Returns 401 if JWT token is missing or invalid
    """
    # Check if path requires JWT authentication
    path = request.url.path
    requires_auth = any(path.startswith(protected) for protected in PROTECTED_PATHS)
    
    if requires_auth and settings.mongodb_enabled:
        # Check if user was authenticated by JWT middleware
        current_user = getattr(request.state, "user", None)
        
        if current_user is None:
            # No valid JWT token found
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authentication required. Please provide a valid JWT token in Authorization header.",
                    "error_code": "AUTHENTICATION_REQUIRED",
                    "hint": "Get a token by logging in at /api/v1/auth/login"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    response = await call_next(request)
    return response

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# JWT Authentication middleware
@app.middleware("http")
async def jwt_authentication_middleware(request: Request, call_next):
    """Extract and validate JWT token, add user to request.state"""
    from app.api.middleware import jwt_auth_middleware
    
    # Extract JWT and populate request.state.user
    await jwt_auth_middleware(request)
    
    response = await call_next(request)
    return response


# Request ID middleware for distributed tracing
@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    """Add request ID and process time tracking"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add headers for debugging and monitoring
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    
    # Structured logging
    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_ip": request.client.host if request.client else None
        }
    )
    
    return response


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # HSTS for HTTPS
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


# GZip compression (60-80% response size reduction)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted hosts middleware (production security)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # TODO: Configure with actual production domains
    )

# CORS middleware - restrictive in production
allowed_origins = ["*"] if settings.debug else [
    "https://yourdomain.com",  # TODO: Add actual production domains
    "https://app.yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow needed methods
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
    max_age=600  # Cache preflight requests for 10 minutes
)


# Global exception handlers
@app.exception_handler(MarksheetExtractionError)
async def marksheet_extraction_error_handler(
    request: Request, 
    exc: MarksheetExtractionError
):
    """Handle custom extraction errors"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Extraction error: {exc.message}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": exc.message,
            "error_code": exc.error_code,
            "details": exc.details if settings.debug else {},
            "request_id": request_id
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unexpected exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.exception(
        f"Unhandled exception: {exc}",
        extra={"request_id": request_id}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR",
            "details": {"message": str(exc)} if settings.debug else {},
            "request_id": request_id
        }
    )


# Static file mounts
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount testdata directory for demo files
testdata_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "testdata")
if os.path.exists(testdata_dir):
    app.mount("/testdata", StaticFiles(directory=testdata_dir), name="testdata")

# API routes 
app.include_router(api_router, prefix="/api", tags=["Extraction"])

# Auth routes (if MongoDB enabled)
if settings.mongodb_enabled:
    from app.api.v1.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-powered marksheet data extraction API",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": {
            "extract_sync": "/api/v1/extract",
            "extract_async": "/api/v1/extract/async",
            "job_status": "/api/v1/job/{job_id}/status",
            "job_result": "/api/v1/job/{job_id}/result",
            "batch": "/api/v1/extract/batch"
        }
    }


# Demo page route
@app.get("/demo", tags=["Demo"])
async def demo_page():
    """Redirect to demo page"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/demo.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=False  # Use custom logging instead
    )
