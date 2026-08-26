import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from celery.exceptions import OperationalError

# Ensure src and root are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

# Autouse fixture to mock RedisCacheManager globally for pipeline tests
@pytest.fixture(autouse=True)
def mock_redis_cache():
    with patch('pipeline.RedisCacheManager') as mock_class:
        mock_instance = MagicMock()
        mock_instance.get_transcript.return_value = None
        mock_instance.set_transcript.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance

@patch('main.run_video_pipeline.delay')
def test_create_job_success(mock_delay):
    # Mock delay to return a mock task
    mock_task = MagicMock()
    mock_task.id = "mock_task_id"
    mock_delay.return_value = mock_task
    
    with TestClient(app) as client:
        response = client.post(
            "/jobs",
            json={
                "link": "https://youtu.be/dgMKzky9S4I",
                "phrase": "good night"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "mock_task_id"
        assert data["status"] == "queued"
        mock_delay.assert_called_once_with("https://youtu.be/dgMKzky9S4I", "good night")

@patch('main.run_video_pipeline.delay')
def test_create_job_operational_error(mock_delay):
    # Mock delay to raise OperationalError (simulating Redis down)
    mock_delay.side_effect = OperationalError("Connection refused")
    
    with TestClient(app) as client:
        response = client.post(
            "/jobs",
            json={
                "link": "https://youtu.be/dgMKzky9S4I",
                "phrase": "good night"
            }
        )
        
        assert response.status_code == 500
        assert "verify Redis is running" in response.json()["detail"]

@patch('main.AsyncResult')
def test_get_job_status_queued(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "PENDING"
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "queued"

@patch('main.AsyncResult')
def test_get_job_status_processing(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "PROCESSING"
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "processing"

@patch('main.AsyncResult')
def test_get_job_status_completed(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "SUCCESS"
    mock_res.result = {
        "timestamp": "00:02:01.410",
        "frame_number": 3682,
        "text": "My mind rebels at stagnation",
        "frame": "base64_data"
    }
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "completed"
        assert data["result"]["timestamp"] == "00:02:01.410"
        assert data["result"]["frame_number"] == 3682
        assert data["result"]["text"] == "My mind rebels at stagnation"
        assert data["result"]["frame"] == "base64_data"

@patch('main.AsyncResult')
def test_get_job_status_failed(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "FAILURE"
    mock_res.result = "ValueError: Target phrase not found in transcription."
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "failed"
        assert data["error_code"] == "PHRASE_NOT_FOUND"
        assert "Target phrase not found" in data["error"]

@patch('main.AsyncResult')
def test_get_job_status_failed_rate_limit(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "FAILURE"
    mock_res.result = "ValueError: Rate limit or network blocking detected on the target website."
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "failed"
        assert data["error_code"] == "RATE_LIMIT_OR_BLOCKED"
        assert "Rate limit" in data["error"]

@patch('main.AsyncResult')
def test_get_job_status_failed_invalid_url(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "FAILURE"
    mock_res.result = "ValueError: The provided video link is invalid or unsupported by the system."
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "failed"
        assert data["error_code"] == "INVALID_OR_UNSUPPORTED_URL"
        assert "invalid or unsupported" in data["error"]

@patch('main.AsyncResult')
def test_get_job_status_failed_unavailable(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "FAILURE"
    mock_res.result = "ValueError: The video is private, removed, or unavailable."
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "failed"
        assert data["error_code"] == "VIDEO_UNAVAILABLE"
        assert "private, removed, or unavailable" in data["error"]

@patch('main.AsyncResult')
def test_get_job_status_failed_ssl(mock_async_result):
    mock_res = MagicMock()
    mock_res.state = "FAILURE"
    mock_res.result = "ValueError: SSL certificate verification failed on the target website."
    mock_async_result.return_value = mock_res
    
    with TestClient(app) as client:
        response = client.get("/jobs/test_job_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test_job_id"
        assert data["status"] == "failed"
        assert data["error_code"] == "SSL_VERIFICATION_FAILED"
        assert "SSL certificate verification" in data["error"]
