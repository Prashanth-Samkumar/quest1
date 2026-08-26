import os
import json
from dataclasses import asdict
from typing import List, Optional
import redis

from schemas import WordTiming
import config
from utils import singleton, get_redis_url

@singleton
class RedisCacheManager:
    """
    Manages caching of transcripts in Redis.
    Uses 7-day TTL expiration, and attempts to configure volatile-lfu eviction.
    """
    def __init__(self):
        self.enabled = True
        try:
            redis_url = get_redis_url(config.REDIS_URL)

            # Initialize Redis connection using variables from config
            self.client = redis.from_url(
                redis_url,
                username=config.REDIS_USERNAME,
                password=config.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=3.0,  # 3 seconds timeout for fast failover
                socket_connect_timeout=3.0
            )
            # Try setting volatile-lfu eviction policy.
            # If server doesn't allow CONFIG SET (e.g. managed cloud Redis), catch and log warning.
            try:
                self.client.config_set("maxmemory-policy", "volatile-lfu")
                print("ℹ️ Redis eviction policy set to volatile-lfu successfully.")
            except redis.exceptions.ResponseError as err:
                print(f"⚠️ Could not set Redis eviction policy to volatile-lfu (not allowed by provider): {err}")
            except Exception as e:
                print(f"⚠️ Failed to dynamically configure Redis maxmemory-policy: {e}")
                
        except Exception as e:
            print(f"❌ Failed to connect to Redis cache manager: {e}. Running in bypass mode.")
            self.enabled = False
            self.client = None

    def get_transcript(self, link: str) -> Optional[List[WordTiming]]:
        """
        Gets a cached transcript list of WordTiming objects from Redis for a given video link.
        """
        if not self.enabled or not self.client:
            return None

        try:
            key = f"transcript:{link}"
            cached_data = self.client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                return [
                    WordTiming(
                        word=item['word'],
                        start=item['start'],
                        end=item['end'],
                        segment_text=item['segment_text']
                    )
                    for item in data
                ]
            return None
        except Exception as e:
            print(f"⚠️ Redis cache read error for link {link}: {e}")
            return None

    def set_transcript(self, link: str, word_timings: List[WordTiming]) -> bool:
        """
        Caches the word timing list in Redis for 7 days (604800 seconds).
        """
        if not self.enabled or not self.client:
            return False

        try:
            key = f"transcript:{link}"
            serialized = json.dumps([asdict(w) for w in word_timings])
            # Set key with TTL = 7 days (604800 seconds)
            result = self.client.set(key, serialized, ex=604800)
            return bool(result)
        except Exception as e:
            print(f"⚠️ Redis cache write error for link {link}: {e}")
            return False
