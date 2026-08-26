from schemas import WordTiming
from faster_whisper import WhisperModel
from typing import List
import os
import sys

def transcribe_audio(audio_path: str, model ) -> List[WordTiming]:
    print(audio_path)
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,   
    )

    word_timings: List[WordTiming] = []
    for segment in segments:
        if segment.words is None:
            continue
        for w in segment.words:
            word_timings.append(
                WordTiming(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    segment_text=segment.text.strip(),
                )
            )

    return word_timings


