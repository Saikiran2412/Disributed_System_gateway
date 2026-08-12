from fastapi import FastAPI, Request, HTTPException
from app.proxy import forward_request
from app.rate_limiter import is_allowed

app = FastAPI(title="Distributed API Gateway")

@app.get("/health")
async def health():
    return {"status": "gateway is up"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(request: Request, path: str):
    client_id = request.client.host

    allowed, remaining = await is_allowed(client_id)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")

    return await forward_request(request)