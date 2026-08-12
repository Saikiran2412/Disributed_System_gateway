import os
from dotenv import load_dotenv

load_dotenv()

UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://localhost:8001")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Rate limit settings
BUCKET_CAPACITY = 5          # max tokens (burst size)
REFILL_RATE = 1              # tokens added per REFILL_INTERVAL
REFILL_INTERVAL = 2          # seconds