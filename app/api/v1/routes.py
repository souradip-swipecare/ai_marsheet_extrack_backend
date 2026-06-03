
import time
from typing import List, Optional, Union, Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Query, Request
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime
from bson import ObjectId

from app.models.schemas import (
    ExtractionResponse,
    BatchExtractionResponse,
    HealthResponse,
    ErrorResponse,
    MarksheetExtraction,
    JobSubmitResponse,
    JobStatusResponse,
    JobResultResponse,
    BatchSubmitResponse,
    BatchJobInfo
)
from app.models.user_schemas import (
    UserActivityLog,
    ExtractionLogCreate,
    ExtractionLogUpdate
)
from app.services.extraction import llm_service
from app.services.ocr_service import ocr_service
from app.services.quality_analyzer import quality_analyzer
from app.services.logging_service import logging_service
from app.services.user_service import user_service
from app.utils.file_processor import file_processor
from app.utils.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    FileProcessingError,
    LLMExtractionError
)
from app.core.config import settings

# Conditional imports for Celery (only if enabled)
if settings.celery_enabled:
    from app.core.celery_config import celery_app
    from app.tasks.extraction_tasks import extract_marksheet_task
else:
    celery_app = None
    extract_marksheet_task = None

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API and LLM service health status",
    tags=["Health"]
)
async def health_check():
    try:
        llm_healthy, provider = await llm_service.health_check()
        return HealthResponse(
            status="healthy" if llm_healthy else "degraded",
            version=settings.app_version,
            llm_provider=provider,
            llm_status="connected" if llm_healthy else "disconnected"
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="unhealthy",
            version=settings.app_version,
            llm_provider=settings.default_llm_provider,
            llm_status=f"error: {str(e)}"
        )


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or request"},
        401: {"model": ErrorResponse, "description": "Authentication required (JWT token missing or invalid)"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Extraction failed"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Extract Marksheet Data",
    description="""Extract structured data from marksheet images or PDFs.
    
    **Authentication**: JWT token required when MongoDB is enabled. 
    Provide `Authorization: Bearer <token>` header.
    
    **Supported Formats**: JPG, JPEG, PNG, PDF (max 10MB)
    
    **Processing**: Automatic quality detection and optimal method selection
    """,
    tags=["Extraction"]
)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def extract_marksheet(
    request: Request,
    file: UploadFile = File(..., description="Marksheet file (JPG, PNG, or PDF)"),
    apikey: Optional[str] = Query(default=None, description="Your Gemini API key. If not provided, server default key will be used."),
    model: str = Query(default="gemini", description="llm model to use. Currently only 'gemini' is supported.")
):

    start_time = time.time()
    extraction_method = "unknown"
    extraction_log_id = None
    user_id = None
    
    # Get user info from middleware (request.state.user)
    current_user = getattr(request.state, "user", None)
    if current_user and settings.mongodb_enabled:
        user_id = current_user["user_id"]
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log user activity
        await logging_service.log_user_activity(UserActivityLog(
            user_id=ObjectId(user_id),
            action="extract",
            details={"filename": file.filename, "sync": True},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            timestamp=datetime.utcnow()
        ))
        
        logger.info(f"Authenticated request from user {user_id}")
    
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        logger.info(f"Processing file: {file.filename} ({file_size} bytes)")
        
        # Create extraction log if user authenticated
        if user_id and settings.mongodb_enabled:
            extraction_log_id = await logging_service.create_extraction_log(
                ExtractionLogCreate(
                    user_id=ObjectId(user_id),
                    job_id=request_id,
                    filename=file.filename,
                    file_size_bytes=file_size,
                    extraction_method="pending",
                    status="processing",
                    request_id=request_id
                )
            )
        
        # check file type
        file_processor.validate_file(
            filename=file.filename,
            file_size=file_size,
            content_type=file.content_type
        )
        
        processed = await file_processor.process_file_smart(file_content, file.filename)
        file_type = processed["type"]
        
        ocr_results = []
        total_ocr_confidence = 0.0
        avg_ocr_confidence = 0.0
        images = []
        quality_info = None
        
        if file_type == "text_pdf":
            extraction_method = "text_pdf_direct"
            text_content = processed["text_content"]
            
            for idx, text in enumerate(text_content):
                ocr_results.append({
                    "page": idx + 1,
                    "text": text,
                    "avg_confidence": 0.99,
                })
                total_ocr_confidence += 0.99
            
            avg_ocr_confidence = total_ocr_confidence / len(ocr_results) if ocr_results else 0.0
            extraction = await llm_service.extract_marksheet_ocr(ocr_results, user_api_key=apikey)
            
        else:
            images = processed["images"]
            
            # assess quality of first image to decide routing
            if not images or len(images) == 0:
                raise FileProcessingError("No images extracted from file")
            
            first_image_bytes, _ = images[0]
            quality_info = quality_analyzer.assess_quality(first_image_bytes)
            
            logger.info(f"Image quality: {quality_info['quality_score']}, path: {quality_info['recommended_path']}")
            
            if quality_info["can_use_ocr"]:
                # high quality - use OCR path (cheaper, faster)
                for idx, (image_bytes, mime_type) in enumerate(images):
                    ocr_data = ocr_service.extract_text(image_bytes, save_text=True)
                    ocr_results.append({
                        "page": idx + 1,
                        "text": ocr_data["raw_text"],
                        "avg_confidence": ocr_data["avg_confidence"],
                    })
                    total_ocr_confidence += ocr_data["avg_confidence"]
                
                avg_ocr_confidence = total_ocr_confidence / len(ocr_results) if ocr_results else 0.0
                
                if avg_ocr_confidence >= settings.ocr_confidence_threshold:
                    extraction_method = "ocr_text_llm"
                    extraction = await llm_service.extract_marksheet_ocr(ocr_results, user_api_key=apikey)
                else:
                    # ocr failed despite good quality, fallback to vision
                    extraction_method = "vision_ocr_fallback"
                    extraction = await llm_service.extract_marksheet(images, user_api_key=apikey)
            else:
                # low quality - skip OCR, go straight to vision
                extraction_method = "vision_direct"
                extraction = await llm_service.extract_marksheet(images, user_api_key=apikey)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Update extraction log with success
        if extraction_log_id and settings.mongodb_enabled:
            cost_map = {
                "text_pdf_direct": 0.00005,
                "ocr_text_llm": 0.00006,
                "vision_direct": 0.0003,
                "vision_ocr_fallback": 0.0003
            }
            
            await logging_service.update_extraction_log(
                extraction_log_id,
                ExtractionLogUpdate(
                    extraction_method=extraction_method,
                    status="completed",
                    extraction_data=extraction.model_dump() if hasattr(extraction, 'model_dump') else extraction,
                    extraction_confidence=extraction.overall_confidence if hasattr(extraction, 'overall_confidence') else None,
                    processing_time_ms=int(processing_time),
                    cost_estimate_usd=cost_map.get(extraction_method, 0.0001)
                )
            )
            
            # Increment user extraction count
            await user_service.increment_extraction_count(ObjectId(user_id))
            
            # Update API usage stats
            await logging_service.update_api_usage_stats(
                ObjectId(user_id),
                success=True,
                processing_time_ms=int(processing_time),
                cost_usd=cost_map.get(extraction_method, 0.0001)
            )
        
        response_data = {
            "success": True,
            "data": extraction,
            "processing_time_ms": round(processing_time, 2),
            "file_name": file.filename,
            "extraction_method": extraction_method,
            "ocr_confidence": round(avg_ocr_confidence, 3),
            "quality_score": quality_info["quality_score"] if quality_info else None,
        }
        
        return response_data
        
    except FileTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
    except InvalidFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except LLMExtractionError as e:
        logger.error(f"LLM extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract data: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error during extraction: {e}")
        
        # Log failure
        if extraction_log_id and settings.mongodb_enabled:
            await logging_service.update_extraction_log(
                extraction_log_id,
                ExtractionLogUpdate(
                    status="failed",
                    error=str(e)
                )
            )
            
            # Update API usage with failure
            if user_id:
                await logging_service.update_api_usage_stats(
                    ObjectId(user_id),
                    success=False,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    cost_usd=0.0
                )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        await file.close()


@router.post(
    "/extract/async",
    response_model=JobSubmitResponse,
    summary="Submit Async Extraction Job",
    description="""Submit extraction job to background queue (Celery).
    
    **Authentication**: JWT token required when MongoDB is enabled.
    
    Returns immediately with job_id. Use `/job/{job_id}/status` to check progress.
    """,
    tags=["Extraction", "Jobs"]
)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def submit_extraction_job(
    request: Request,
    file: UploadFile = File(...),
    apikey: Optional[str] = Query(default=None)
):
    try:
        if not settings.celery_enabled:
            raise HTTPException(
                status_code=503,
                detail="Async processing not enabled. Set CELERY_ENABLED=true and start worker."
            )
        
        file_content = await file.read()
        file_size = len(file_content)
        
        file_processor.validate_file(
            filename=file.filename,
            file_size=file_size,
            content_type=file.content_type
        )
        
        task = extract_marksheet_task.delay(file_content, file.filename, apikey)
        
        # Log activity if authenticated (from middleware)
        current_user = getattr(request.state, "user", None)
        if current_user and settings.mongodb_enabled:
            await logging_service.log_user_activity(UserActivityLog(
                user_id=ObjectId(current_user["user_id"]),
                action="extract_async",
                details={"filename": file.filename, "job_id": task.id},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                timestamp=datetime.utcnow()
            ))
        
        return JobSubmitResponse(
            success=True,
            job_id=task.id,
            status="queued",
            message="Job submitted. Use /job/{job_id}/status to check progress.",
            estimated_time_seconds=30
        )
        
    except Exception as e:
        logger.error(f"Job submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()


@router.get(
    "/job/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Check Job Status",
    description="""Get current status and progress of an async extraction job.
    
    **Job States**: queued, processing, completed, failed
    """,
    tags=["Jobs"]
)
async def get_job_status(job_id: str):
    try:
        now = datetime.utcnow().isoformat()
        
        task = celery_app.AsyncResult(job_id)
        
        if task.state == 'PENDING':
            return JobStatusResponse(
                success=True,
                job_id=job_id,
                status="queued",
                progress=0,
                created_at=now,
                updated_at=now
            )
        elif task.state == 'PROCESSING':
            return JobStatusResponse(
                success=True,
                job_id=job_id,
                status="processing",
                progress=task.info.get('progress', 0),
                created_at=now,
                updated_at=now
            )
        elif task.state == 'SUCCESS':
            return JobStatusResponse(
                success=True,
                job_id=job_id,
                status="completed",
                progress=100,
                created_at=now,
                updated_at=now
            )
        elif task.state == 'FAILURE':
            return JobStatusResponse(
                success=True,
                job_id=job_id,
                status="failed",
                progress=0,
                created_at=now,
                updated_at=now,
                error=str(task.info)
            )
        else:
            return JobStatusResponse(
                success=True,
                job_id=job_id,
                status=task.state.lower(),
                progress=0,
                created_at=now,
                updated_at=now
            )
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/job/{job_id}/result",
    response_model=JobResultResponse,
    summary="Get Job Result",
    description="""Retrieve extraction result for a completed job.
    
    **Note**: Returns 202 if job is still processing.
    """,
    tags=["Jobs"]
)
async def get_job_result(job_id: str):
    try:
        task = celery_app.AsyncResult(job_id)
        
        if task.state == 'PENDING':
            raise HTTPException(status_code=202, detail="Job still queued")
        elif task.state == 'PROCESSING':
            raise HTTPException(status_code=202, detail="Job still processing")
        elif task.state == 'FAILURE':
            return JobResultResponse(
                success=False,
                data=None,
                filename="unknown",
                extraction_method="failed",
                cost_estimate_usd=0.0,
                error=str(task.info)
            )
        elif task.state == 'SUCCESS':
            # Task result should already be properly formatted
            return JobResultResponse(**task.result)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown state: {task.state}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Result fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/extract/batch",
    response_model=Union[BatchSubmitResponse, BatchExtractionResponse],
    summary="Batch Extract Marksheets",
    description="""Upload multiple marksheets for batch processing.
    
    **Authentication**: JWT token required when MongoDB is enabled.
    
    **Limit**: Maximum 10 files per batch
    
    **Behavior**:
    - If Celery enabled: Returns immediately with job IDs (async)
    - If Celery disabled: Processes synchronously and returns results
    """,
    tags=["Batch", "Extraction"]
)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def batch_extract_marksheets(
    request: Request,
    files: List[UploadFile] = File(..., description="List of marksheet files"),
    apikey: Optional[str] = Query(default=None, description="Your Gemini API key (optional)")
):
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed per batch request"
        )
    
    # Log batch activity if authenticated (from middleware)
    current_user = getattr(request.state, "user", None)
    if current_user and settings.mongodb_enabled:
        await logging_service.log_user_activity(UserActivityLog(
            user_id=ObjectId(current_user["user_id"]),
            action="batch_extract",
            details={"file_count": len(files), "async": settings.celery_enabled},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            timestamp=datetime.utcnow()
        ))
    
    # if celery enabled, submit all as async jobs
    if settings.celery_enabled:
        try:
            job_ids = []
            
            for file in files:
                file_content = await file.read()
                file_size = len(file_content)
                
                file_processor.validate_file(
                    filename=file.filename,
                    file_size=file_size,
                    content_type=file.content_type
                )
                
                task = extract_marksheet_task.delay(file_content, file.filename, apikey)
                
                job_ids.append(BatchJobInfo(
                    filename=file.filename,
                    job_id=task.id,
                    status="queued"
                ))
                
                await file.close()
            
            return BatchSubmitResponse(
                success=True,
                batch_id=f"batch_{int(time.time())}",
                total_files=len(files),
                jobs=job_ids,
                message="All jobs submitted. Use /batch/{batch_id}/status or individual /job/{job_id}/status"
            )
            
        except Exception as e:
            logger.error(f"Batch submission failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # fallback to sync processing if celery disabled
    start_time = time.time()
    results = []
    successful = 0
    failed = 0
    
    for file in files:
        file_start = time.time()
        
        try:
            file_content = await file.read()
            file_size = len(file_content)
            
            file_processor.validate_file(
                filename=file.filename,
                file_size=file_size,
                content_type=file.content_type
            )
            
            # process
            images = await file_processor.process_file(file_content, file.filename)
            
            # Extract
            extraction = await llm_service.extract_marksheet(images, user_api_key=apikey)
            
            processing_time = (time.time() - file_start) * 1000
            
            results.append(ExtractionResponse(
                success=True,
                data=extraction,
                processing_time_ms=round(processing_time, 2),
                file_name=file.filename,
                file_size_bytes=file_size
            ))
            successful += 1
            
        except Exception as e:
            logger.error(f"Batch extraction failed for {file.filename}: {e}")
            processing_time = (time.time() - file_start) * 1000
            
            results.append(ExtractionResponse(
                success=False,
                data=None,
                error=str(e),
                processing_time_ms=round(processing_time, 2),
                file_name=file.filename,
                file_size_bytes=len(await file.read()) if file else 0
            ))
            failed += 1
            
        finally:
            await file.close()
    
    total_time = (time.time() - start_time) * 1000
    
    return BatchExtractionResponse(
        success=failed == 0,
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=results,
        total_processing_time_ms=round(total_time, 2)
    )

@router.post(
    "/batch/{batch_id}/status",
    summary="Check Batch Status",
    description="""Check status of all jobs in a batch.
    
    Provide job IDs as query parameters to check their status.
    """,
    tags=["Batch"]
)
async def check_batch_status_endpoint(
    batch_id: str,
    job_ids: List[str] = Query(..., description="List of job IDs to check")
):
    """check status of multiple jobs at once"""
    try:
        results = []
        completed = 0
        processing = 0
        failed = 0
        queued = 0
        
        for job_id in job_ids:
            task = celery_app.AsyncResult(job_id)
            
            if task.state == 'PENDING':
                status = 'queued'
                queued += 1
            elif task.state == 'PROCESSING':
                status = 'processing'
                processing += 1
            elif task.state == 'SUCCESS':
                status = 'completed'
                completed += 1
            elif task.state == 'FAILURE':
                status = 'failed'
                failed += 1
            else:
                status = task.state.lower()
            
            results.append({
                "job_id": job_id,
                "status": status,
                "progress": task.info.get('progress', 0) if task.state == 'PROCESSING' else (100 if status == 'completed' else 0)
            })
        
        total = len(job_ids)
        overall_progress = int((completed / total) * 100) if total > 0 else 0
        
        return {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "queued": queued,
            "overall_progress": overall_progress,
            "jobs": results
        }
        
    except Exception as e:
        logger.error(f"Batch status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/batch/{batch_id}/results",
    summary="Get All Batch Results",
    description="""Retrieve results for all completed jobs in a batch.
    
    Provide job IDs as query parameters.
    """,
    tags=["Batch"]
)
async def get_batch_results(
    batch_id: str,
    job_ids: List[str] = Query(..., description="List of job IDs")
):
    """get results for all jobs in batch"""
    try:
        results = []
        
        for job_id in job_ids:
            task = celery_app.AsyncResult(job_id)
            
            if task.state == 'SUCCESS':
                result = task.result
                results.append({
                    "job_id": job_id,
                    "status": "completed",
                    "data": result
                })
            elif task.state == 'FAILURE':
                results.append({
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(task.info)
                })
            else:
                results.append({
                    "job_id": job_id,
                    "status": task.state.lower(),
                    "data": None
                })
        
        return {
            "batch_id": batch_id,
            "total": len(job_ids),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch results fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/schema",
    summary="Get Response Schema",
    description="""Get the JSON schema for the extraction response format.
    
    Useful for understanding the structure of extracted data.
    """,
    tags=["Schema"]
)
async def get_schema():
    """Return the JSON schema for marksheet extraction response"""
    return MarksheetExtraction.model_json_schema()
