import sys
import os
import logging
from contextlib import asynccontextmanager

# Add src directory to path so imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from celery.result import AsyncResult
from celery.exceptions import OperationalError

from celery_app import celery_app, run_video_pipeline

# Setup standard logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class ProcessRequest(BaseModel):
    link: str
    phrase: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log FastAPI startup. Note: WhisperModel is loaded in the Celery worker process now.
    logger.info("Starting FastAPI Web Server...")
    yield
    logger.info("Shutting down FastAPI Web Server...")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Quest1 Background Task API Server",
    description="FastAPI service utilizing Celery and Redis to process videos in the background.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(req: ProcessRequest):
    logger.info(f"Submitting background job: link='{req.link}', phrase='{req.phrase}'")
    try:
        task = run_video_pipeline.delay(req.link, req.phrase)
        return {
            "job_id": task.id,
            "status": "queued"
        }
    except (OperationalError, Exception) as e:
        logger.error(f"Failed to submit task to Celery queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit task to background queue. Please verify Redis is running."
        )

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    logger.info(f"Retrieving status for job ID: {job_id}")
    try:
        res = AsyncResult(job_id, app=celery_app)
        state = res.state
        
        if state == "SUCCESS":
            return {
                "job_id": job_id,
                "status": "completed",
                "result": res.result
            }
        elif state == "FAILURE":
            # Return safe error messages derived from task failure
            error_msg = str(res.result) if res.result else "Internal task execution failed."
            error_code = "INTERNAL_ERROR"
            if "invalid or unsupported" in error_msg:
                error_code = "INVALID_OR_UNSUPPORTED_URL"
            elif "private, removed, or unavailable" in error_msg:
                error_code = "VIDEO_UNAVAILABLE"
            elif "Rate limit" in error_msg or "network blocking" in error_msg:
                error_code = "RATE_LIMIT_OR_BLOCKED"
            elif "SSL certificate verification" in error_msg:
                error_code = "SSL_VERIFICATION_FAILED"
            elif "not found" in error_msg:
                error_code = "PHRASE_NOT_FOUND"
                
            return {
                "job_id": job_id,
                "status": "failed",
                "error_code": error_code,
                "error": error_msg
            }
        elif state in ("PROCESSING", "STARTED"):
            return {
                "job_id": job_id,
                "status": "processing"
            }
        else:
            # Map PENDING and other queued/received states to queued
            return {
                "job_id": job_id,
                "status": "queued"
            }
    except (OperationalError, Exception) as e:
        logger.error(f"Failed to query result backend for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task status from background backend. Please verify Redis is running."
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
