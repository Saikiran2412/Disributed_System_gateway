import time
from app.redis_client import redis_client

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 15

async def get_state(service_key: str) -> dict:
    data = await redis_client.hgetall(f"circuit:{service_key}")
    if not data:
        return {"state": "closed", "failures": 0, "opened_at": 0}
    return {
        "state": data.get("state", "closed"),
        "failures": int(data.get("failures", 0)),
        "opened_at": float(data.get("opened_at", 0)),
    }

async def record_success(service_key: str):
    await redis_client.hset(f"circuit:{service_key}", mapping={
        "state": "closed",
        "failures": 0,
        "opened_at": 0,
    })

async def record_failure(service_key: str):
    state = await get_state(service_key)
    failures = state["failures"] + 1

    if failures >= FAILURE_THRESHOLD:
        await redis_client.hset(f"circuit:{service_key}", mapping={
            "state": "open",
            "failures": failures,
            "opened_at": time.time(),
        })
    else:
        await redis_client.hset(f"circuit:{service_key}", mapping={
            "state": "closed",
            "failures": failures,
            "opened_at": 0,
        })

async def can_proceed(service_key: str) -> bool:
    state = await get_state(service_key)

    if state["state"] == "closed":
        return True

    if state["state"] == "open":
        elapsed = time.time() - state["opened_at"]
        if elapsed >= COOLDOWN_SECONDS:
            await redis_client.hset(f"circuit:{service_key}", mapping={"state": "half_open"})
            return True
        return False

    if state["state"] == "half_open":
        return True

    return True