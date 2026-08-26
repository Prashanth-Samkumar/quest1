from dataclasses import dataclass

@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    segment_text: str
    
@dataclass
class MatchCandidate:
    matched_text: str
    score: float
    start_time: float
    end_time: float
    window_word_count: int
