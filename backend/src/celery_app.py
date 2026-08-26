import os
import sys
import base64
import logging
from celery import Celery

# Ensure src and root directories are in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from pipeline import run_pipeline
from utils import format_timestamp, get_redis_url, cleanup_files_for_link

# Setup standard logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Parse and clean redis url
redis_url = get_redis_url(config.REDIS_URL)

# Initialize Celery app
celery_app = Celery(
    "tasks",
    broker=redis_url,
    backend=redis_url
)

# Apply configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_expires=86400,  # 1 day result expiration
)

_model = None

def get_whisper_model():
    """
    Lazy loader for WhisperModel, ensuring it is initialized once per Celery worker process.
    """
    global _model
    if _model is None:
        logger.info("Initializing WhisperModel on CPU (once per worker process)...")
        from faster_whisper import WhisperModel
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("WhisperModel successfully initialized!")
    return _model

@celery_app.task(bind=True, name="run_video_pipeline", throws=(ValueError,))
def run_video_pipeline(self, link: str, phrase: str):
    logger.info(f"Celery Task {self.request.id} started. Link: {link}, Phrase: {phrase}")
    
    # Custom status update
    self.update_state(state='PROCESSING')
    
    try:
        model = get_whisper_model()
        match_candidates, frame_number, frame_path = run_pipeline(link, phrase, model)
        
        if not match_candidates:
            # We raise ValueError when phrase not found so the Celery task goes into FAILURE state,
            # which GET /jobs/{job_id} will catch and return as status="failed" with the error message.
            raise ValueError("Target phrase not found in transcription.")
            
        # Get the highest-scoring candidate (at index 0)
        best_match = match_candidates[0]
        formatted_time = format_timestamp(best_match.start_time)
        
        # Read and base64-encode the frame image
        base64_frame = ""
        if frame_path and os.path.exists(frame_path):
            try:
                with open(frame_path, "rb") as img_file:
                    base64_frame = base64.b64encode(img_file.read()).decode("utf-8")
            except Exception as read_err:
                logger.error(f"Error reading frame image {frame_path}: {read_err}")
                
        result = {
            "timestamp": formatted_time,
            "frame_number": frame_number if frame_number is not None else 0,
            "text": best_match.matched_text,
            "frame": base64_frame
        }
        
        logger.info(f"Celery Task {self.request.id} completed successfully.")
        return result
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"Celery Task {self.request.id} failed: {error_str}")
        
        # Translate exceptions into user-friendly errors
        unsupported_url_terms = ["Unsupported URL", "not a valid URL", "RegexNotFoundError", "Name or service not known", "HTTP Error 404"]
        rate_limit_terms = ["10054", "429", "rate limit", "Rate Limit", "Forbidden", "forbidden", 
                            "Unable to download webpage", "connection was forcibly closed"]
        video_unavailable_terms = ["Video unavailable", "Private video", "This video has been removed"]
        ssl_terms = ["CERTIFICATE_VERIFY_FAILED", "unable to get local issuer certificate", "SSLError", "CertificateVerifyError"]
        
        if any(term in error_str for term in unsupported_url_terms):
            clean_error = "The provided video link is invalid or unsupported by the system."
        elif any(term in error_str for term in video_unavailable_terms):
            clean_error = "The video is private, removed, or unavailable."
        elif any(term in error_str for term in rate_limit_terms):
            clean_error = "Rate limit or network blocking detected on the target website. Please try again later."
        elif any(term in error_str for term in ssl_terms):
            clean_error = "SSL certificate verification failed on the target website."
        else:
            clean_error = f"Pipeline execution failed: {error_str}"
            
        raise ValueError(clean_error) from None
    # finally:
    #     logger.info(f"Performing filesystem cleanup for task {self.request.id}...")
    #     cleanup_files_for_link(link)
