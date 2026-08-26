import yt_dlp
import subprocess
import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_video_duration(url, retries: int = 50):
    """
    Get the duration of a video without downloading it.
    
    Args:
        url (str): Video URL
        retries (int): Number of download retries
        
    Returns:
        float: Duration in seconds
        
    Raises:
        Exception: If duration cannot be retrieved
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': url,
            'retries': retries,
            'fragment_retries': retries,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise Exception("Could not retrieve video information")
                
            duration = info.get('duration')
            
            if duration is None:
                raise Exception("Could not get video duration")
                
            return float(duration)
            
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"Failed to fetch video info: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error getting duration: {str(e)}")

def download_audio(url, output_path="audio.wav", retries: int = 50):
    """
    Download only the best audio quality and convert to WAV.
    
    Args:
        url (str): Video URL
        output_path (str): Output file path (default: audio.wav)
        retries (int): Number of download retries
        
    Returns:
        str: Path to downloaded audio file
        
    Raises:
        Exception: If audio download fails or no audio is available
    """
    try:
        # Download best audio and convert to WAV
        ydl_opts = {
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '0',  # Best quality
            }],
            'outtmpl': output_path.replace('.wav', ''),  # yt-dlp adds extension
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': url,
            'retries': retries,
            'fragment_retries': retries,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except yt_dlp.utils.DownloadError as e:
                raise Exception(f"Audio download failed: {str(e)}")
            
            # Check if file was created
            wav_file = output_path if output_path.endswith('.wav') else f"{output_path}.wav"
            
            import os
            if not os.path.exists(wav_file):
                # Try to find what was actually created
                base_name = output_path.replace('.wav', '')
                if os.path.exists(f"{base_name}.wav"):
                    wav_file = f"{base_name}.wav"
                else:
                    raise Exception("Audio file was not created successfully")
            
            return wav_file
            
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"Audio extraction failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error downloading audio: {str(e)}")

def download_video(
    url: str,
    quality: str = "worst",
    output_path: str = "output/video.mp4",
    parallel_fragments: int = 15,
    retries: int = 50
) -> str:
    """
    Download video with specified quality and parallel fragment download control.
    
    Args:
        url: Video URL
        quality: "worst" or "normal" (default: "worst")
        output_path: Output file path (default: "output/video.mp4")
        parallel_fragments: Number of parallel fragment downloads (default: 1)
            - 1 = Sequential (no parallel)
            - 4-8 = Good balance for fast connections
            - 16-32 = Aggressive parallel downloads
        retries: Number of download retries
    
    Returns:
        str: Path to downloaded video file
    
    Raises:
        Exception: If video download fails or no video is available
    """
    
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Set format based on quality parameter
        if quality.lower() == "worst":
            format_spec = "worstvideo+worstaudio/worst"
        else:
            format_spec = "bestvideo+bestaudio/best"
        
        base_name = Path(output_path).with_suffix('')
        
        ydl_opts = {
            'format': format_spec,
            'merge_output_format': 'mp4',
            'outtmpl': str(base_name),
            'concurrent_fragments': parallel_fragments,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': url,
            'retries': retries,
            'fragment_retries': retries,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find the actual video file
        mp4_file = output_path if output_path.endswith('.mp4') else f"{output_path}.mp4"
        
        if not os.path.exists(mp4_file):
            base_name = Path(output_path).with_suffix('')
            if os.path.exists(str(base_name)):
                try:
                    os.rename(str(base_name), mp4_file)
                except Exception:
                    mp4_file = str(base_name)
            else:
                for ext in ['.mp4', '.mkv', '.webm']:
                    test_path = f"{base_name}{ext}"
                    if os.path.exists(test_path):
                        mp4_file = test_path
                        break
                else:
                    raise Exception("Video file was not created successfully")
        
        return mp4_file
        
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"Video download failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error downloading video: {str(e)}")

def extract_audio(video_path: str, output_path: str = None) -> str:
    """
    Extract audio from video file.
    
    Args:
        video_path: Path to video file
        output_path: Path for audio output (optional)
    
    Returns:
        str: Path to extracted audio file
    """
    
    video_path = Path(video_path)
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    if output_path is None:
        output_path = video_path.with_suffix('.wav')
    
    cmd = [
        'ffmpeg',
        '-i', str(video_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-f', 'wav',
        '-y',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        
        if not Path(output_path).exists():
            raise RuntimeError(f"Audio file was not created: {output_path}")
        
        return str(output_path)
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e.stderr.decode()}")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg is not installed")

def download_clip(
    url: str,
    start_time: float,
    end_time: float,
    output_path: str = "output/clip.mp4",
    quality: str = "worst",
    parallel_fragments: int = 10,
    retries: int = 50
) -> str:
    """
    Download a specific clip from a video using timestamp range.
    
    Args:
        url: Video URL
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Output file path
        quality: "worst" or "normal"
        parallel_fragments: Number of parallel fragment downloads
    
    Returns:
        str: Path to downloaded clip
    
    Raises:
        Exception: If download or clipping fails
    """
    
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    temp_dir = output_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    temp_video = temp_dir / "full_video.mp4"
    
    try:
        # Download full video
        logger.info("Downloading video...")
        
        if quality.lower() == "worst":
            format_spec = "worstvideo+worstaudio/worst"
        else:
            format_spec = "bestvideo+bestaudio/best"
        
        ydl_opts = {
            'format': format_spec,
            'merge_output_format': 'mp4',
            'outtmpl': str(temp_video.with_suffix('')),
            'concurrent_fragments': parallel_fragments,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': url,
            'retries': retries,
            'fragment_retries': retries,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find actual video file
        actual_video = None
        base_name = temp_video.with_suffix('')
        target_path = temp_video.parent / f"{base_name.name}.mp4"
        
        if temp_video.exists():
            actual_video = temp_video
        elif base_name.exists():
            try:
                base_name.rename(target_path)
                actual_video = target_path
            except Exception:
                actual_video = base_name
        else:
            for ext in ['.mp4', '.mkv', '.webm']:
                test_path = Path(f"{base_name}{ext}")
                if test_path.exists():
                    actual_video = test_path
                    break
        
        if not actual_video:
            raise Exception("Video download failed")
        
        logger.info(f"Video downloaded: {actual_video}")
        logger.info(f"Clipping from {start_time}s to {end_time}s...")
        
        # Clip video using ffmpeg
        duration = end_time - start_time
        
        cmd = [
            'ffmpeg',
            '-i', str(actual_video),
            '-ss', str(start_time),
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', '1',
            '-y',
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        if not Path(output_path).exists():
            raise Exception("Clipping failed")
        
        logger.info(f"Clip saved: {output_path}")
        
        # Clean up temp files
        if actual_video.exists():
            actual_video.unlink()
        temp_dir.rmdir()
        
        return str(output_path)
        
    except subprocess.CalledProcessError as e:
        raise Exception(f"ffmpeg clipping failed: {e.stderr.decode()}")
    except Exception as e:
        raise Exception(f"Clip download failed: {str(e)}")

from yt_dlp.utils import download_range_func

def download_clip_only(
    url: str,
    start_time: float,  # in seconds
    end_time: float,    # in seconds
    output_path: str = "output/clip.mp4",
    quality: str = "worst",
    retries: int = 50
) -> str:
    """
    Download ONLY the clip without downloading the full video.
    
    Args:
        url: Video URL
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Output file path
        quality: "worst" or "normal"
    
    Returns:
        str: Path to downloaded clip
    """
    
    if quality.lower() == "worst":
        format_spec = "worstvideo+worstaudio/worst"
    else:
        format_spec = "bestvideo+bestaudio/best"
    
    ydl_opts = {
        'format': format_spec,
        'merge_output_format': 'mp4',
        'outtmpl': output_path,
        'download_ranges': download_range_func(None, [(start_time, end_time)]),
        'force_keyframes_at_cuts': True,  # Required for precise cuts
        'quiet': True,
        'no_warnings': True,
        'retries': retries,
        'fragment_retries': retries,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    return output_path

# Example usage
if __name__ == "__main__":
    test_url = "https://ok.ru/video/248244667877"
    
    try:
        # # 1. Get duration
        # print("Getting duration...")
        # duration = get_video_duration(test_url)
        # print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        
        # # # 2. Download audio (best quality)
        # # print("\nDownloading best audio...")
        # # audio_file = download_best_audio(test_url, "audio.wav")
        # # print(f"Audio saved to: {audio_file}")
        
        # # 3. Download video (worst quality for testing)
        # print("\nDownloading video (worst quality)...")
        # video_file = download_video(test_url, "worst", "video_worst.mp4")
        # print(f"Video saved to: {video_file}")
        
        # # Alternative: Download normal quality
        # # print("\nDownloading video (normal quality)...")
        # # video_normal = download_video(test_url, "normal", "video_normal.mp4")
        # # print(f"Video saved to: {video_normal}")
        # print("extracting...")
        # audio_path = extract_audio(video_file)
        # print(f"Audio saved to: {audio_path}")

        # print("done")
        clip = download_clip_only(
            url=test_url,
            start_time=150.0,
            end_time=1550.0,
            output_path="output/clip.mp4",
            quality="worst"
        )
        print(f"Clip saved: {clip}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)