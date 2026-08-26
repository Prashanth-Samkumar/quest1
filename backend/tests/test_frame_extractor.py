import pytest
import os
import sys
import subprocess
import json
from unittest.mock import patch, MagicMock

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from frame_extractor import parse_timestamp, get_video_fps, extract_frame

# --- Tests for parse_timestamp ---

def test_parse_timestamp_numeric():
    assert parse_timestamp(12.34) == 12.34
    assert parse_timestamp(42) == 42.0
    assert parse_timestamp("123.45") == 123.45
    assert parse_timestamp("60") == 60.0

def test_parse_timestamp_mm_ss():
    assert parse_timestamp("01:23") == 83.0
    assert parse_timestamp("10:00") == 600.0
    assert parse_timestamp("0:45.5") == 45.5

def test_parse_timestamp_hh_mm_ss():
    assert parse_timestamp("01:02:03") == 3723.0
    assert parse_timestamp("00:00:10.5") == 10.5

def test_parse_timestamp_invalid():
    with pytest.raises(ValueError):
        parse_timestamp("invalid")
    with pytest.raises(ValueError):
        parse_timestamp("12:34:56:78")
    with pytest.raises(TypeError):
        parse_timestamp([1, 2])


# --- Tests for get_video_fps ---

@patch('subprocess.run')
def test_get_video_fps_avg(mock_run):
    # Setup mock output
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "streams": [{
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "30/1"
            }]
        }),
        stderr=""
    )
    fps = get_video_fps("dummy_path.mp4")
    assert pytest.approx(fps, 0.001) == 29.97

@patch('subprocess.run')
def test_get_video_fps_fallback(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "streams": [{
                "avg_frame_rate": "0/0",
                "r_frame_rate": "25/1"
            }]
        }),
        stderr=""
    )
    fps = get_video_fps("dummy_path.mp4")
    assert fps == 25.0

@patch('subprocess.run')
def test_get_video_fps_no_streams(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "streams": []
        }),
        stderr=""
    )
    with pytest.raises(ValueError, match="No video streams found"):
        get_video_fps("dummy_path.mp4")

@patch('subprocess.run')
def test_get_video_fps_failure(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd="ffprobe",
        stderr="Error opening file"
    )
    with pytest.raises(RuntimeError, match="ffprobe failed"):
        get_video_fps("dummy_path.mp4")


# --- Tests for extract_frame ---

@patch('frame_extractor.get_video_fps')
@patch('os.path.exists')
@patch('os.makedirs')
@patch('subprocess.run')
def test_extract_frame_success(mock_run, mock_makedirs, mock_exists, mock_fps):
    # Setup mocks
    # We pretend the local video file exists
    mock_exists.side_effect = lambda path: os.path.basename(path) in ("dummy_video.mp4", "dummy_video_frame_150.png")
    mock_fps.return_value = 30.0
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    frame_num, frame_path = extract_frame("dummy_video.mp4", 5.0, output_dir="output")
    
    # Assertions
    assert frame_num == 150
    assert frame_path.replace("\\", "/").endswith("output/dummy_video_frame_150.png")
    
    # Verify ffmpeg arguments
    mock_run.assert_called_with(
        [
            'ffmpeg',
            '-ss', '4.600000',
            '-i', 'dummy_video.mp4',
            '-ss', '0.400000',
            '-frames:v', '1',
            '-q:v', '2',
            '-y',
            frame_path
        ],
        capture_output=True,
        text=True,
        check=True
    )

@patch('frame_extractor.get_video_fps')
@patch('os.path.exists')
@patch('os.makedirs')
@patch('subprocess.run')
def test_extract_frame_near_zero(mock_run, mock_makedirs, mock_exists, mock_fps):
    mock_exists.side_effect = lambda path: os.path.basename(path) in ("dummy_video.mp4", "dummy_video_frame_6.png")
    mock_fps.return_value = 30.0
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    frame_num, frame_path = extract_frame("dummy_video.mp4", 0.2, output_dir="output")
    
    assert frame_num == 6
    assert frame_path.replace("\\", "/").endswith("output/dummy_video_frame_6.png")
    
    mock_run.assert_called_with(
        [
            'ffmpeg',
            '-ss', '0.000000',
            '-i', 'dummy_video.mp4',
            '-ss', '0.200000',
            '-frames:v', '1',
            '-q:v', '2',
            '-y',
            frame_path
        ],
        capture_output=True,
        text=True,
        check=True
    )

@patch('os.path.exists')
def test_extract_frame_missing_video(mock_exists):
    mock_exists.return_value = False
    
    with pytest.raises(FileNotFoundError, match="Video file not found"):
        extract_frame("missing_video.mp4", 5.0)
