import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the root project directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Redis configurations
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_USERNAME = os.getenv("redis_username") or os.getenv("REDIS_USERNAME") or "default"
REDIS_PASSWORD = os.getenv("redis_password") or os.getenv("REDIS_PASSWORD")


