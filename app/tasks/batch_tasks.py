from typing import Dict, List
from celery import group
from app.core.celery_config import celery_app


@celery_app.task(name="check_batch_status")
def check_batch_status(job_ids: List[str]) -> Dict:
    """check status of multiple jobs in a batch"""
    
    results = []
    completed = 0
    processing = 0
    failed = 0
    queued = 0
    
    for job_id in job_ids:
        task = celery_app.AsyncResult(job_id)
        
        status_map = {
            'PENDING': 'queued',
            'PROCESSING': 'processing',
            'SUCCESS': 'completed',
            'FAILURE': 'failed'
        }
        
        status = status_map.get(task.state, task.state.lower())
        
        if status == 'completed':
            completed += 1
        elif status == 'processing':
            processing += 1
        elif status == 'failed':
            failed += 1
        else:
            queued += 1
        
        results.append({
            "job_id": job_id,
            "status": status
        })
    
    total = len(job_ids)
    overall_progress = int((completed / total) * 100) if total > 0 else 0
    
    return {
        "total": total,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "queued": queued,
        "progress": overall_progress,
        "jobs": results
    }
