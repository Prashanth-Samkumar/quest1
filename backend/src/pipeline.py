import os
import sys
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import List

# Ensure src and root directories are in path when executing
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faster_whisper import WhisperModel
from schemas import MatchCandidate, WordTiming
from downloader import get_video_duration, download_audio, download_video, extract_audio, download_clip_only
from transcriber import transcribe_audio
from matcher import fuzzy_match
from utils import get_video_filename, get_audio_filename, get_transcript_filename
from frame_extractor import extract_frame
from cache_manager import RedisCacheManager

logger = logging.getLogger(__name__)

def resolve_overlapping_candidates(candidates: List[MatchCandidate]) -> List[MatchCandidate]:
    """
    Groups candidates that overlap in time. For each overlapping group,
    selects the candidate with the highest matching score.
    Non-overlapping candidates are kept as separate single-element groups.
    """
    if not candidates:
        return []
        
    # Sort candidates by start_time ascending
    sorted_candidates = sorted(candidates, key=lambda x: x.start_time)
    
    groups = []
    current_group = [sorted_candidates[0]]
    
    for next_cand in sorted_candidates[1:]:
        # Since sorted by start_time, next_cand.start_time >= any start_time in current_group.
        # They overlap if next_cand.start_time <= max(end_time of current_group)
        current_group_end = max(c.end_time for c in current_group)
        if next_cand.start_time <= current_group_end:
            current_group.append(next_cand)
        else:
            groups.append(current_group)
            current_group = [next_cand]
            
    if current_group:
        groups.append(current_group)
        
    # For each group, select the candidate with the highest matching score.
    # Tie-breaker: earlier start_time
    best_candidates = []
    for gp in groups:
        best_cand = max(gp, key=lambda x: (x.score, -x.start_time))
        best_candidates.append(best_cand)
        
    # Sort selected candidates by start_time ascending
    best_candidates.sort(key=lambda x: x.start_time)
    return best_candidates

def run_pipeline(link: str, phases: str, model) -> List[MatchCandidate]:
    """
    Runs the full pipeline:
    1. Checks if transcript JSON exists. If so, skips downloading/transcribing and directly performs matching.
    2. Gets the video duration.
    3. If duration is < 30 minutes, downloads the video and extracts audio.
    4. If duration is >= 30 minutes, downloads only audio. Fallback to video download + extraction if audio download fails.
    5. Transcribes the audio.
    6. Performs fuzzy matching of target phrase (phases).
    7. Returns the match candidates.
    
    Args:
        link (str): The video URL.
        phases (str): The target phrase to match in the transcription.
        model: WhisperModel instance.
        
    Returns:
        List[MatchCandidate]: Fuzzy match results.
    """
    logger.info(f"Starting pipeline for video: {link}")
    logger.info(f"Target phrase: {phases}")
    
    # Generate dynamic paths based on link
    video_path = get_video_filename(link)
    audio_path = get_audio_filename(link)
    json_path = get_transcript_filename(link)
    
    # Initialize cache manager
    cache_mgr = RedisCacheManager()
    
    # Check Redis cache first
    word_timings = cache_mgr.get_transcript(link)
    
    if word_timings:
        logger.info(f"Found existing transcription in Redis cache for: {link}. Skipping download and transcription.")
    else:
        # Check if the transcript already exists locally
        if os.path.exists(json_path):
            logger.info(f"Found existing transcription JSON: {json_path}. Skipping download and transcription.")
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                word_timings = [
                    WordTiming(
                        word=item['word'],
                        start=item['start'],
                        end=item['end'],
                        segment_text=item['segment_text']
                    ) for item in data
                ]
                logger.info(f"Loaded {len(word_timings)} words from existing local transcript.")
                # Cache local transcript to Redis for subsequent runs
                cache_mgr.set_transcript(link, word_timings)
            except Exception as e:
                logger.warning(f"Failed to load existing local transcript: {e}. Re-running full pipeline.")
                word_timings = None
            
    if word_timings is None:
        # 1. Get video duration
        logger.info("Stage 1: Getting video duration...")
        try:
            duration = get_video_duration(link)
            logger.info(f"Stage 1 Complete: Video duration is {duration:.2f} seconds ({duration / 60:.2f} minutes)")
        except Exception as e:
            logger.warning(f"Stage 1 Warning: Could not get video duration: {e}. Defaulting to full video download.")
            duration = 0.0
            
        # 2. Download based on duration (30 mins = 1800 seconds)
        if duration > 0.0 and duration < 1800.0:
            logger.info("Stage 2: Video is under 30 minutes. Downloading the full video...")
            try:
                video_path = download_video(link, quality="worst", output_path=video_path)
                logger.info(f"Stage 2 Complete: Video downloaded to: {video_path}")
                logger.info("Stage 3: Extracting audio from video...")
                audio_path = extract_audio(video_path, output_path=audio_path)
                logger.info(f"Stage 3 Complete: Audio extracted to: {audio_path}")
            except Exception as e:
                logger.error(f"Failed to download video or extract audio: {e}")
                logger.info("Falling back to downloading only audio...")
                try:
                    audio_path = download_audio(link, output_path=audio_path)
                    logger.info(f"Stage 2 & 3 (Fallback) Complete: Audio downloaded to: {audio_path}")
                except Exception as audio_err:
                    logger.error(f"Audio-only download fallback failed: {audio_err}")
                    raise audio_err
        else:
            if duration >= 1800.0:
                logger.info("Stage 2 & 3: Video is 30 minutes or longer. Attempting to download only audio...")
            else:
                logger.info("Stage 2 & 3: Unknown/zero duration. Attempting to download only audio...")
                
            try:
                audio_path = download_audio(link, output_path=audio_path)
                logger.info(f"Stage 2 & 3 Complete: Audio downloaded to: {audio_path}")
            except Exception as audio_err:
                logger.warning(f"Audio-only download failed: {audio_err}")
                logger.info("Falling back to downloading the full video and extracting audio...")
                try:
                    video_path = download_video(link, quality="worst", output_path=video_path)
                    logger.info(f"Stage 2 (Fallback) Complete: Video downloaded to: {video_path}")
                    logger.info("Stage 3 (Fallback): Extracting audio from video...")
                    audio_path = extract_audio(video_path, output_path=audio_path)
                    logger.info(f"Stage 3 (Fallback) Complete: Audio extracted to: {audio_path}")
                except Exception as fallback_err:
                    logger.error(f"Fallback download and extraction failed: {fallback_err}")
                    raise fallback_err

        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError(f"Could not locate downloaded/extracted audio file: {audio_path}")
            
        # 3. Transcribe audio
        logger.info("Stage 4: Starting audio transcription...")
        word_timings = transcribe_audio(audio_path, model)
        logger.info(f"Stage 4 Complete: Transcription complete. Total words: {len(word_timings)}")
        
        # Save transcription to Redis cache
        cache_mgr.set_transcript(link, word_timings)
        
        # Save transcription to a JSON file
        try:
            data_to_save = [asdict(w) for w in word_timings]
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved transcription JSON to: {json_path}")
        except Exception as e:
            logger.warning(f"Warning: Could not save transcription JSON: {e}")
    
    # 4. Fuzzy Match
    logger.info(f"Stage 5: Performing fuzzy matching for phrase: '{phases}'")
    match_candidates = fuzzy_match(word_timings, phases)
    logger.info(f"Stage 5 Complete: Fuzzy matching complete. Matches found: {len(match_candidates)}")
    
    # Resolve overlapping candidates, selecting the highest scoring one from each overlapping group
    match_candidates = resolve_overlapping_candidates(match_candidates)
    logger.info(f"Overlap Resolution Complete: Reduced to {len(match_candidates)} unique matches.")
    
    frame_number = None
    frame_path = None
    
    if match_candidates:
        # Select the first match from the resolved non-overlapping candidates list
        first_match = match_candidates[0]
        
        # Check if the full video exists locally
        from utils import get_clean_id
        clean_id = get_clean_id(link)
        video_path_default = get_video_filename(link)
        actual_video_path = None
        
        if os.path.exists(video_path_default):
            actual_video_path = video_path_default
        else:
            base_path = Path(video_path_default).with_suffix('')
            for ext in ('.mp4', '.mkv', '.webm', '.avi'):
                test_path = base_path.with_suffix(ext)
                if test_path.exists():
                    actual_video_path = str(test_path)
                    break
                    
        if actual_video_path:
            logger.info(f"Video exists locally at: {actual_video_path}. Extracting frame...")
            try:
                frame_number, frame_path = extract_frame(actual_video_path, first_match.start_time + 1)
                logger.info(f"Frame extracted: number {frame_number}, path: {frame_path}")
            except Exception as e:
                logger.error(f"Failed to extract frame from existing video: {e}")
        else:
            logger.info("Video does not exist locally. Downloading clip to extract frame...")
            # We clip the video from first_match.start_time to first_match.end_time
            # Ensure folder exists
            os.makedirs("output", exist_ok=True)
            clip_filename = f"{clean_id}_clip_{int(first_match.start_time)}_{int(first_match.end_time)}.mp4"
            clip_path = f"output/{clip_filename}"
            
            try:
                # If clip already exists, skip download
                if not os.path.exists(clip_path):
                    logger.info(f"Downloading clip from {first_match.start_time}s to {first_match.end_time}s...")
                    download_clip_only(
                        url=link,
                        start_time=first_match.start_time,
                        end_time=first_match.end_time,
                        output_path=clip_path
                    )
                
                # Offset the frame extraction timestamp by 0.4 seconds
                frame_number, frame_path = extract_frame(clip_path, 0.4, frame_number_offset_seconds=first_match.start_time)
                logger.info(f"Frame extracted: number {frame_number}, path: {frame_path}")
            except Exception as e:
                logger.error(f"Failed to download clip or extract frame: {e}")
                
    return match_candidates, frame_number, frame_path

if __name__ == "__main__":
    print("started")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("model loaded")
    print(run_pipeline("https://youtu.be/dgMKzky9S4I", "good night", model))