import sys
import os

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from schemas import WordTiming
from matcher import fuzzy_match

def test_fuzzy_match_exact():
    word_timings = [
        WordTiming(word="hello", start=0.0, end=0.5, segment_text="hello world"),
        WordTiming(word="world", start=0.5, end=1.0, segment_text="hello world"),
    ]
    matches = fuzzy_match(word_timings, "hello world")
    assert len(matches) > 0
    assert matches[0].matched_text == "hello world"
    assert matches[0].start_time == 0.0
    assert matches[0].end_time == 1.0

def test_fuzzy_match_approximate():
    word_timings = [
        WordTiming(word="hello", start=0.0, end=0.5, segment_text="hello world"),
        WordTiming(word="word", start=0.5, end=1.0, segment_text="hello world"),  # ASR typo
    ]
    matches = fuzzy_match(word_timings, "hello world", score_threshold=80.0)
    assert len(matches) > 0
    assert matches[0].matched_text == "hello word"
    assert matches[0].score >= 80.0
