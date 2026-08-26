import sys
import os
from unittest.mock import patch, MagicMock
import pytest

# Ensure src and root are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from schemas import MatchCandidate, WordTiming
from pipeline import run_pipeline, resolve_overlapping_candidates

@patch('pipeline.get_video_duration')
@patch('pipeline.download_video')
@patch('pipeline.extract_audio')
@patch('pipeline.transcribe_audio')
@patch('pipeline.fuzzy_match')
@patch('os.path.exists')
@patch('pipeline.download_clip_only')
@patch('pipeline.extract_frame')
def test_pipeline_short_video(
    mock_extract_frame,
    mock_download_clip_only,
    mock_exists,
    mock_fuzzy_match,
    mock_transcribe_audio,
    mock_extract_audio,
    mock_download_video,
    mock_get_video_duration
):
    # Setup
    mock_get_video_duration.return_value = 600.0  # 10 minutes (less than 30 mins)
    mock_download_video.return_value = "output/example_com_short_video.mp4"
    mock_extract_audio.return_value = "output/example_com_short_audio.wav"
    mock_exists.side_effect = lambda path: not path.endswith("_trans.json")
    
    mock_transcribe_audio.return_value = []
    expected_matches = [MatchCandidate(matched_text="hello", score=100.0, start_time=0.0, end_time=1.0, window_word_count=1)]
    mock_fuzzy_match.return_value = expected_matches
    mock_extract_frame.return_value = (150, "output/example_com_short_frame_150.png")
    
    # Run
    mock_model = MagicMock()
    result, frame_num, frame_path = run_pipeline("http://example.com/short", "hello", mock_model)
    
    # Assert
    assert result == expected_matches
    assert frame_num == 150
    assert frame_path == "output/example_com_short_frame_150.png"
    
    mock_get_video_duration.assert_called_once_with("http://example.com/short")
    mock_download_video.assert_called_once_with("http://example.com/short", quality="worst", output_path="output/example_com_short_video.mp4")
    mock_extract_audio.assert_called_once_with("output/example_com_short_video.mp4", output_path="output/example_com_short_audio.wav")
    mock_transcribe_audio.assert_called_once_with("output/example_com_short_audio.wav", mock_model)
    mock_fuzzy_match.assert_called_once_with([], "hello")
    mock_extract_frame.assert_called_once_with("output/example_com_short_video.mp4", 1.0)
    mock_download_clip_only.assert_not_called()

@patch('pipeline.get_video_duration')
@patch('pipeline.download_audio')
@patch('pipeline.transcribe_audio')
@patch('pipeline.fuzzy_match')
@patch('os.path.exists')
@patch('pipeline.download_clip_only')
@patch('pipeline.extract_frame')
def test_pipeline_long_video_audio_success(
    mock_extract_frame,
    mock_download_clip_only,
    mock_exists,
    mock_fuzzy_match,
    mock_transcribe_audio,
    mock_download_audio,
    mock_get_video_duration
):
    # Setup
    mock_get_video_duration.return_value = 2400.0  # 40 minutes (more than 30 mins)
    mock_download_audio.return_value = "output/example_com_long_audio.wav"
    
    # Force mock_exists to return False for JSON, video, and clip, but True for audio
    def exists_side_effect(path):
        # Normalize slashes for comparison
        normalized = path.replace("\\", "/")
        if normalized.endswith("_trans.json") or normalized.endswith("_video.mp4") or "clip" in normalized:
            return False
        return True
    mock_exists.side_effect = exists_side_effect
    
    mock_transcribe_audio.return_value = []
    expected_matches = [MatchCandidate(matched_text="world", score=95.0, start_time=1.0, end_time=2.0, window_word_count=1)]
    mock_fuzzy_match.return_value = expected_matches
    mock_download_clip_only.return_value = "output/example_com_long_clip_1_2.mp4"
    mock_extract_frame.return_value = (30, "output/example_com_long_frame_30.png")
    
    # Run
    mock_model = MagicMock()
    result, frame_num, frame_path = run_pipeline("http://example.com/long", "world", mock_model)
    
    # Assert
    assert result == expected_matches
    assert frame_num == 30
    assert frame_path == "output/example_com_long_frame_30.png"
    
    mock_get_video_duration.assert_called_once_with("http://example.com/long")
    mock_download_audio.assert_called_once_with("http://example.com/long", output_path="output/example_com_long_audio.wav")
    mock_transcribe_audio.assert_called_once_with("output/example_com_long_audio.wav", mock_model)
    mock_download_clip_only.assert_called_once_with(
        url="http://example.com/long",
        start_time=1.0,
        end_time=2.0,
        output_path="output/example_com_long_clip_1_2.mp4"
    )
    mock_extract_frame.assert_called_once_with("output/example_com_long_clip_1_2.mp4", 0.4, frame_number_offset_seconds=1.0)

@patch('pipeline.get_video_duration')
@patch('pipeline.download_audio')
@patch('pipeline.download_video')
@patch('pipeline.extract_audio')
@patch('pipeline.transcribe_audio')
@patch('pipeline.fuzzy_match')
@patch('os.path.exists')
@patch('pipeline.download_clip_only')
@patch('pipeline.extract_frame')
def test_pipeline_long_video_audio_fail_fallback(
    mock_extract_frame,
    mock_download_clip_only,
    mock_exists,
    mock_fuzzy_match,
    mock_transcribe_audio,
    mock_extract_audio,
    mock_download_video,
    mock_download_audio,
    mock_get_video_duration
):
    # Setup
    mock_get_video_duration.return_value = 2400.0  # 40 minutes
    mock_download_audio.side_effect = Exception("Audio download failed")
    mock_download_video.return_value = "output/example_com_long_fail_video.mp4"
    mock_extract_audio.return_value = "output/example_com_long_fail_audio.wav"
    mock_exists.side_effect = lambda path: not path.endswith("_trans.json")
    
    mock_transcribe_audio.return_value = []
    expected_matches = []
    mock_fuzzy_match.return_value = expected_matches
    
    # Run
    mock_model = MagicMock()
    result, frame_num, frame_path = run_pipeline("http://example.com/long_fail", "world", mock_model)
    
    # Assert
    assert result == expected_matches
    assert frame_num is None
    assert frame_path is None
    
    mock_get_video_duration.assert_called_once_with("http://example.com/long_fail")
    mock_download_audio.assert_called_once_with("http://example.com/long_fail", output_path="output/example_com_long_fail_audio.wav")
    mock_download_video.assert_called_once_with("http://example.com/long_fail", quality="worst", output_path="output/example_com_long_fail_video.mp4")
    mock_extract_audio.assert_called_once_with("output/example_com_long_fail_video.mp4", output_path="output/example_com_long_fail_audio.wav")
    mock_transcribe_audio.assert_called_once_with("output/example_com_long_fail_audio.wav", mock_model)
    mock_extract_frame.assert_not_called()
    mock_download_clip_only.assert_not_called()

@pytest.fixture(autouse=True)
def mock_redis_cache():
    with patch('pipeline.RedisCacheManager') as mock_class:
        mock_instance = MagicMock()
        mock_instance.get_transcript.return_value = None
        mock_instance.set_transcript.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance

@patch('pipeline.fuzzy_match')
@patch('pipeline.extract_frame')
def test_pipeline_cache_hit(mock_extract_frame, mock_fuzzy_match):
    # Test that run_pipeline uses cached transcript and skips download/transcribe entirely
    with patch('pipeline.RedisCacheManager') as mock_class:
        mock_cache = MagicMock()
        word_timings = [WordTiming(word="cached", start=1.0, end=2.0, segment_text="cached text")]
        mock_cache.get_transcript.return_value = word_timings
        mock_class.return_value = mock_cache
        
        expected_matches = [MatchCandidate(matched_text="cached", score=100.0, start_time=1.0, end_time=2.0, window_word_count=1)]
        mock_fuzzy_match.return_value = expected_matches
        mock_extract_frame.return_value = (10, "output/cached_frame.png")
        
        with patch('pipeline.get_video_duration') as mock_dur, \
             patch('pipeline.download_video') as mock_down_vid, \
             patch('pipeline.extract_audio') as mock_ext_aud, \
             patch('pipeline.download_audio') as mock_down_aud, \
             patch('pipeline.transcribe_audio') as mock_trans, \
             patch('pipeline.download_clip_only') as mock_down_clip:
             
            mock_model = MagicMock()
            result, frame_num, frame_path = run_pipeline("http://example.com/cached", "cached", mock_model)
            
            assert result == expected_matches
            assert frame_num == 10
            assert frame_path == "output/cached_frame.png"
            
            # Verify cache get was called
            mock_cache.get_transcript.assert_called_once_with("http://example.com/cached")
            
            # Verify download and transcription were completely skipped
            mock_dur.assert_not_called()
            mock_down_vid.assert_not_called()
            mock_ext_aud.assert_not_called()
            mock_down_aud.assert_not_called()
            mock_trans.assert_not_called()
            mock_down_clip.assert_called_once()

def test_resolve_overlapping_candidates():
    # 1. Overlapping candidates: A and B overlap, B has higher score. C is non-overlapping.
    cand_a = MatchCandidate(matched_text="a", score=80.0, start_time=1.0, end_time=3.0, window_word_count=2)
    cand_b = MatchCandidate(matched_text="b", score=95.0, start_time=2.0, end_time=4.0, window_word_count=2)
    cand_c = MatchCandidate(matched_text="c", score=90.0, start_time=5.0, end_time=6.0, window_word_count=1)
    
    # 2. Overlapping candidates where scores are equal (should select earlier one as tie-breaker)
    cand_d = MatchCandidate(matched_text="d", score=85.0, start_time=7.0, end_time=9.0, window_word_count=2)
    cand_e = MatchCandidate(matched_text="e", score=85.0, start_time=8.0, end_time=10.0, window_word_count=2)
    
    input_candidates = [cand_a, cand_b, cand_c, cand_d, cand_e]
    
    result = resolve_overlapping_candidates(input_candidates)
    
    # Expected results:
    # - Group 1 (cand_a, cand_b): cand_b selected (score 95.0 > 80.0)
    # - Group 2 (cand_c): cand_c selected
    # - Group 3 (cand_d, cand_e): cand_d selected (tie-breaker: start_time 7.0 < 8.0)
    
    assert len(result) == 3
    assert result[0] == cand_b
    assert result[1] == cand_c
    assert result[2] == cand_d


