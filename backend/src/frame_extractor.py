import os
import subprocess
import json
from pathlib import Path
from typing import Tuple, Union
from utils import get_video_filename, get_clean_id

def parse_timestamp(ts: Union[float, int, str]) -> float:
    """
    Parse timestamp into float seconds.
    Supports float, int, and formats like 'HH:MM:SS', 'MM:SS', or numeric strings.
    """
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        # Check if HH:MM:SS or MM:SS format
        parts = ts.split(':')
        if len(parts) in (2, 3):
            try:
                if len(parts) == 2:
                    m, s = map(float, parts)
                    return m * 60 + s
                else:
                    h, m, s = map(float, parts)
                    return h * 3600 + m * 60 + s
            except ValueError:
                pass
        try:
            return float(ts)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {ts}")
    raise TypeError(f"Timestamp must be float, int or str, got {type(ts)}")

def get_video_fps(video_path: str) -> float:
    """
    Get the frame rate (FPS) of a video file using ffprobe.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate,avg_frame_rate',
        '-of', 'json',
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed to read video metadata: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("ffprobe is not installed or not in PATH")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError("Failed to parse ffprobe metadata as JSON")

    streams = data.get('streams', [])
    if not streams:
        raise ValueError("No video streams found in the file")

    for key in ('avg_frame_rate', 'r_frame_rate'):
        val = streams[0].get(key)
        if val:
            try:
                if '/' in val:
                    num, den = map(float, val.split('/'))
                    if den != 0:
                        return num / den
                else:
                    return float(val)
            except (ValueError, ZeroDivisionError):
                continue
    raise ValueError("Could not determine frame rate from video streams")

def extract_frame(link_or_path: str, timestamp: Union[float, int, str], output_dir: str = "output", frame_number_offset_seconds: float = 0.0) -> Tuple[int, str]:
    """
    Extracts a frame from a video given a link or local path and a timestamp.
    
    Args:
        link_or_path (str): The video link/URL or local video file path.
        timestamp (Union[float, int, str]): The timestamp of the frame (in seconds or HH:MM:SS format).
        output_dir (str): Directory where the frame image will be saved.
        
    Returns:
        Tuple[int, str]: A tuple containing (frame_number, saved_frame_path).
        
    Raises:
        FileNotFoundError: If the video file does not exist.
        ValueError: If frame extraction fails.
    """
    # 1. Resolve actual video path
    video_path = link_or_path
    clean_id = None
    
    # Check if link_or_path is a local file directly
    if not os.path.exists(video_path):
        # Try to resolve via get_video_filename
        default_path = get_video_filename(link_or_path)
        if os.path.exists(default_path):
            video_path = default_path
            clean_id = get_clean_id(link_or_path)
        else:
            # Try other extensions
            base_path = Path(default_path).with_suffix('')
            for ext in ('.mp4', '.mkv', '.webm', '.avi'):
                test_path = base_path.with_suffix(ext)
                if test_path.exists():
                    video_path = str(test_path)
                    clean_id = get_clean_id(link_or_path)
                    break
            else:
                # Check if it was just a local path that doesn't exist
                raise FileNotFoundError(f"Video file not found at '{video_path}' or derived path '{default_path}'")

    if not clean_id:
        # It's a local file path that exists, clean the filename to get clean ID
        clean_id = Path(video_path).stem

    # 2. Parse timestamp and compute frame number
    ts_seconds = parse_timestamp(timestamp)
    fps = get_video_fps(video_path)
    frame_number = int(round((ts_seconds + frame_number_offset_seconds) * fps))

    # 3. Create output directory and build frame output path
    os.makedirs(output_dir, exist_ok=True)
    frame_filename = f"{clean_id}_frame_{frame_number}.png"
    frame_path = os.path.abspath(os.path.join(output_dir, frame_filename))

    # 4. Extract frame using ffmpeg (two-stage seek)
    if ts_seconds < 0.4:
        ss1 = 0.0
        ss2 = ts_seconds
    else:
        ss1 = ts_seconds - 0.4
        ss2 = 0.4

    cmd = [
        'ffmpeg',
        '-ss', f"{ss1:.6f}",
        '-i', video_path,
        '-ss', f"{ss2:.6f}",
        '-frames:v', '1',
        '-q:v', '2',
        '-y',
        frame_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg frame extraction failed: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg is not installed or not in PATH")

    if not os.path.exists(frame_path):
        raise RuntimeError(f"ffmpeg command completed, but output frame file was not created: {frame_path}")

    return frame_number, os.path.abspath(frame_path)
