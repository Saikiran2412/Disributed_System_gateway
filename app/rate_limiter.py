import time
from app.redis_client import redis_client
from app.config import BUCKET_CAPACITY, REFILL_RATE, REFILL_INTERVAL

TOKEN_BUCKET_SCRIPT = '''
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local refill_interval = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
local refill_amount = math.floor(elapsed / refill_interval) * refill_rate
tokens = math.min(capacity, tokens + refill_amount)
if refill_amount > 0 then
    last_refill = now
end

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, refill_interval * capacity * 2)

return {allowed, tokens}
'''

async def is_allowed(client_id: str) -> tuple[bool, int]:
    now = int(time.time())
    result = await redis_client.eval(
        TOKEN_BUCKET_SCRIPT,
        1,
        f"rate_limit:{client_id}",
        BUCKET_CAPACITY,
        REFILL_RATE,
        REFILL_INTERVAL,
        now,
    )
    allowed, remaining_tokens = result
    return bool(allowed), remaining_tokens
