from fastapi import FastAPI, Request, HTTPException
from app.proxy import forward_request
from app.rate_limiter import is_allowed
from app.auth import authenticate
from app.circuit_breaker import can_proceed, record_success, record_failure
from app.logging_middleware import LoggingMiddleware
from app.sliding_window import is_allowed_sliding

app = FastAPI(title="Distributed API Gateway")
app.add_middleware(LoggingMiddleware)

UPSTREAM_SERVICE_KEY = "smart_router_chatbot"

@app.get("/health")
async def health():
    return {"status": "gateway is up"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(request: Request, path: str):
    client_id = await authenticate(request)

    algorithm = request.headers.get("X-RateLimit-Algorithm", "token_bucket")

    if algorithm == "sliding_window":
        allowed, count = await is_allowed_sliding(client_id)
    else:
        allowed, count = await is_allowed(client_id)

    if not allowed:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({algorithm}). Try again shortly.")
    
    if not await can_proceed(UPSTREAM_SERVICE_KEY):
        raise HTTPException(status_code=503, detail="Upstream service unavailable (circuit open). Try again shortly.")

    try:
        response = await forward_request(request)
        await record_success(UPSTREAM_SERVICE_KEY)
        return response
    except Exception as e:
        await record_failure(UPSTREAM_SERVICE_KEY)
        raise HTTPException(status_code=502, detail="Upstream request failed.")