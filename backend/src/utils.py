import re
import os
import logging

logger = logging.getLogger(__name__)

def singleton(cls):
    instances = {}
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance
def get_clean_id(link: str) -> str:
    """
    Extract a unique, filesystem-safe ID from a video URL.
    Supports YouTube, OK.ru, and falls back to cleaning generic URLs.
    """
    # Try to extract YouTube video ID (11 chars)
    yt_match = re.search(r'(?:v=|\/)([a-zA-Z0-9_-]{11})(?:\?|&|$)', link)
    if yt_match:
        return yt_match.group(1)
        
    # Try to extract OK.ru video ID
    ok_match = re.search(r'video\/(\d+)', link)
    if ok_match:
        return ok_match.group(1)
        
    # Fallback to general clean link
    clean_link = re.sub(r'https?://(?:www\.)?', '', link)
    clean_link = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_link)
    return clean_link[:50]

def get_video_filename(link: str) -> str:
    """Get the video filename path for a given link."""
    return f"output/{get_clean_id(link)}_video.mp4"

def get_audio_filename(link: str) -> str:
    """Get the audio filename path for a given link."""
    return f"output/{get_clean_id(link)}_audio.wav"

def get_transcript_filename(link: str) -> str:
    """Get the transcript JSON filename path for a given link."""
    return f"output/{get_clean_id(link)}_trans.json"

def format_timestamp(seconds: float) -> str:
    """
    Format float seconds into HH:MM:SS.sss string.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms -= 1000
        s += 1
        if s >= 60:
            s -= 60
            m += 1
            if m >= 60:
                m -= 60
                h += 1
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def get_redis_url(raw_url: str) -> str:
    """
    Cleans and formats a Redis URL, prepending the redis:// scheme,
    embedding username/password if they exist in config/env,
    and extracting ports from Redis Enterprise Cloud hostnames if missing.
    """
    import config
    if not raw_url:
        raw_url = "redis://localhost:6379"
    url = raw_url.strip()
    
    # Strip any existing scheme to clean/rebuild it
    is_ssl = False
    if url.startswith("redis://"):
        url = url[8:]
    elif url.startswith("rediss://"):
        url = url[9:]
        is_ssl = True
    elif url.startswith("unix://"):
        url = url[7:]
        
    # Check if host already has credentials
    if "@" not in url:
        password = getattr(config, "REDIS_PASSWORD", None)
        username = getattr(config, "REDIS_USERNAME", None)
        if password:
            if username:
                url = f"{username}:{password}@{url}"
            else:
                url = f":{password}@{url}"
                
    # Re-prepend scheme
    scheme = "rediss://" if is_ssl else "redis://"
    url = f"{scheme}{url}"
    
    # Check for Redis Cloud endpoint hostname format (e.g. redis-11106...)
    # If port is missing in URL, extract and append it.
    url_without_scheme = url.replace("redis://", "").replace("rediss://", "").replace("unix://", "")
    host_part = url_without_scheme.split("@")[-1]
    if ":" not in host_part:
        match = re.search(r'redis-(\d+)\.', host_part)
        if match:
            port = match.group(1)
            url = url.replace(host_part, f"{host_part}:{port}")
    return url

def cleanup_files_for_link(link: str):
    """
    Deletes all files in the output directory associated with the given link.
    """
    import glob
    clean_id = get_clean_id(link)
    if not clean_id:
        return
        
    pattern = os.path.join("output", f"{clean_id}*")
    files = glob.glob(pattern)
    for f in files:
        try:
            if os.path.isfile(f):
                os.remove(f)
                logger.info(f"Cleaned up file: {f}")
        except Exception as e:
            logger.warning(f"Failed to delete file {f}: {e}")
