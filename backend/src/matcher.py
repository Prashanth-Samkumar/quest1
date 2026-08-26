from typing import List
from rapidfuzz import fuzz
from schemas import WordTiming, MatchCandidate


def fuzzy_match(
    word_timings: List[WordTiming],
    target_phrase: str,
    score_threshold: float = 80.0,
    window_slack: int = 2,
) -> List[MatchCandidate]:

    target_words = target_phrase.strip().split()
    n_target = len(target_words)

    candidates: List[MatchCandidate] = []

    for window_size in range(max(1, n_target - window_slack), n_target + window_slack + 1):
        for i in range(len(word_timings) - window_size + 1):
            window = word_timings[i : i + window_size]
            window_text = " ".join(w.word for w in window)

            score = fuzz.token_sort_ratio(window_text.lower(), target_phrase.lower())

            if score >= score_threshold:
                candidates.append(
                    MatchCandidate(
                        matched_text=window_text,
                        score=score,
                        start_time=window[0].start,
                        end_time=window[-1].end,
                        window_word_count=window_size,
                    )
                )

    candidates.sort(key=lambda c: c.score, reverse=True)

    deduped: List[MatchCandidate] = []
    seen_times: List[float] = []
    for c in candidates:
        if all(abs(c.start_time - t) > 1.0 for t in seen_times):
            deduped.append(c)
            seen_times.append(c.start_time)

    return deduped