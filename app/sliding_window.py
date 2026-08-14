import time
from app.redis_client import redis_client

WINDOW_SECONDS = 10
MAX_REQUESTS = 5

SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local current_window = math.floor(now / window)
local current_key = key .. ':' .. current_window
local previous_key = key .. ':' .. (current_window - 1)

local current_count = tonumber(redis.call('GET', current_key)) or 0
local previous_count = tonumber(redis.call('GET', previous_key)) or 0

local elapsed_in_window = (now % window) / window
local weighted_count = (previous_count * (1 - elapsed_in_window)) + current_count

if weighted_count >= max_requests then
    return {0, weighted_count}
end

redis.call('INCR', current_key)
redis.call('EXPIRE', current_key, window * 2)

return {1, weighted_count + 1}
"""

async def is_allowed_sliding(client_id: str) -> tuple[bool, float]:
    now = time.time()
    result = await redis_client.eval(
        SLIDING_WINDOW_SCRIPT,
        1,
        f"sliding:{client_id}",
        WINDOW_SECONDS,
        MAX_REQUESTS,
        now,
    )
    allowed, count = result
    return bool(allowed), float(count)