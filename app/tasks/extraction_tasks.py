import asyncio
import time
from typing import Dict, Any
from celery import Task
from loguru import logger

from app.core.celery_config import celery_app
from app.services.extraction import llm_service
from app.services.quality_analyzer import quality_analyzer
from app.utils.file_processor import file_processor
from app.core.config import settings


class CallbackTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")
        
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True, base=CallbackTask, name="extract_marksheet_task")
def extract_marksheet_task(self, file_data: bytes, filename: str, user_api_key: str = None) -> Dict[str, Any]:
    
    try:
        self.update_state(state='PROCESSING', meta={'progress': 10, 'status': 'Starting extraction'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            self.update_state(state='PROCESSING', meta={'progress': 20, 'status': 'Processing file'})
            
            processed = loop.run_until_complete(
                file_processor.process_file_smart(file_data, filename)
            )
            file_type = processed["type"]
            
            self.update_state(state='PROCESSING', meta={'progress': 40, 'status': 'Running extraction'})
            
            extraction_method = "unknown"
            
            if file_type == "text_pdf":
                from app.services.ocr_service import ocr_service
                
                text_content = processed["text_content"]
                ocr_results = [
                    {"page": idx + 1, "text": text, "avg_confidence": 0.99}
                    for idx, text in enumerate(text_content)
                ]
                
                extraction = loop.run_until_complete(
                    llm_service.extract_marksheet_ocr(ocr_results, user_api_key=user_api_key)
                )
                extraction_method = "text_pdf_llm"
                
            else:
                from app.services.ocr_service import ocr_service
                
                
                # quality-based routing
                first_image_bytes, _ = images[0]
                quality_info = quality_analyzer.assess_quality(first_image_bytes)
                
                self.update_state(state='PROCESSING', meta={'progress': 45, 'status': f'Quality: {quality_info["quality_score"]}'})
                
                if quality_info["can_use_ocr"]:
                    # high quality - try OCR path first
                    ocr_results = []
                    total_conf = 0.0
                    
                    self.update_state(state='PROCESSING', meta={'progress': 50, 'status': 'Running OCR'})
                    
                    for idx, (img_bytes, mime) in enumerate(images):
                        ocr_data = ocr_service.extract_text(img_bytes, save_text=False)
                        ocr_results.append({
                            "page": idx + 1,
                            "text": ocr_data["raw_text"],
                            "avg_confidence": ocr_data["avg_confidence"]
                        })
                        total_conf += ocr_data["avg_confidence"]
                    
                    avg_conf = total_conf / len(ocr_results) if ocr_results else 0.0
                    
                    self.update_state(state='PROCESSING', meta={'progress': 70, 'status': 'LLM extraction'})
                    
                    if avg_conf >= settings.ocr_confidence_threshold:
                        extraction = loop.run_until_complete(
                            llm_service.extract_marksheet_ocr(ocr_results, user_api_key=user_api_key)
                        )
                        extraction_method = "ocr_text_llm"
                    else:
                        extraction = loop.run_until_complete(
                            llm_service.extract_marksheet(images, user_api_key=user_api_key)
                        )
                        extraction_method = "vision_ocr_fallback"
                else:
                    # low quality - skip OCR, use vision directly
                    self.update_state(state='PROCESSING', meta={'progress': 60, 'status': 'Vision API extraction'})
                    
                    extraction = loop.run_until_complete(
                        llm_service.extract_marksheet(images, user_api_key=user_api_key)
                    )
                    extraction_method = "vision_direct"
            
            self.update_state(state='PROCESSING', meta={'progress': 90, 'status': 'Finalizing'})
            
            # Calculate cost estimate based on method
            cost_map = {
                "text_pdf_direct": 0.00005,
                "ocr_text_llm": 0.00006,
                "vision_direct": 0.0003,
                "vision_ocr_fallback": 0.0003
            }
            cost_estimate = cost_map.get(extraction_method, 0.0001)
            
            return {
                "success": True,
                "data": extraction,
                "filename": filename,
                "extraction_method": extraction_method,
                "cost_estimate_usd": cost_estimate
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception(f"Extraction task failed: {e}")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "filename": filename,
            "extraction_method": "failed",
            "cost_estimate_usd": 0.0
        }
