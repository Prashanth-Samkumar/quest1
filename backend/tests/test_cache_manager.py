import sys
import os
from unittest.mock import patch, MagicMock
import pytest
import redis

# Ensure src and root are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from cache_manager import RedisCacheManager
from schemas import WordTiming

@pytest.fixture(autouse=True)
def reset_singleton():
    if RedisCacheManager.__closure__:
        for cell in RedisCacheManager.__closure__:
            if isinstance(cell.cell_contents, dict):
                cell.cell_contents.clear()

@patch('redis.from_url')
def test_cache_manager_init(mock_from_url):
    mock_client = MagicMock()
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    assert manager.enabled is True
    mock_from_url.assert_called_once()
    mock_client.config_set.assert_called_once_with("maxmemory-policy", "volatile-lfu")

@patch('redis.from_url')
def test_cache_manager_init_config_error(mock_from_url):
    mock_client = MagicMock()
    mock_client.config_set.side_effect = redis.exceptions.ResponseError("CONFIG SET blocked")
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    assert manager.enabled is True
    mock_client.config_set.assert_called_once_with("maxmemory-policy", "volatile-lfu")

@patch('redis.from_url')
def test_cache_manager_init_connection_error(mock_from_url):
    mock_from_url.side_effect = Exception("Connection refused")
    
    manager = RedisCacheManager()
    assert manager.enabled is False
    assert manager.client is None

@patch('redis.from_url')
def test_get_transcript_cache_miss(mock_from_url):
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    result = manager.get_transcript("http://example.com/video")
    assert result is None
    mock_client.get.assert_called_once_with("transcript:http://example.com/video")

@patch('redis.from_url')
def test_get_transcript_cache_hit(mock_from_url):
    mock_client = MagicMock()
    mock_client.get.return_value = '[{"word": "hello", "start": 1.0, "end": 2.0, "segment_text": "hello"}]'
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    result = manager.get_transcript("http://example.com/video")
    assert len(result) == 1
    assert isinstance(result[0], WordTiming)
    assert result[0].word == "hello"
    assert result[0].start == 1.0
    assert result[0].end == 2.0
    assert result[0].segment_text == "hello"

@patch('redis.from_url')
def test_set_transcript(mock_from_url):
    mock_client = MagicMock()
    mock_client.set.return_value = True
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    timings = [WordTiming(word="test", start=0.5, end=1.5, segment_text="test text")]
    success = manager.set_transcript("http://example.com/video", timings)
    
    assert success is True
    mock_client.set.assert_called_once()
    args, kwargs = mock_client.set.call_args
    assert args[0] == "transcript:http://example.com/video"
    assert "test" in args[1]
    assert kwargs.get("ex") == 604800

@patch('redis.from_url')
def test_graceful_failures(mock_from_url):
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Read timeout")
    mock_client.set.side_effect = Exception("Write timeout")
    mock_from_url.return_value = mock_client
    
    manager = RedisCacheManager()
    assert manager.get_transcript("http://example.com/video") is None
    assert manager.set_transcript("http://example.com/video", []) is False
