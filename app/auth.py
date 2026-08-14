import jwt
from fastapi import Request, HTTPException
from app.redis_client import redis_client
from app.config import JWT_SECRET

async def verify_api_key(request: Request) -> str | None:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
    client_id = await redis_client.hget("api_keys", api_key)
    return client_id

def verify_jwt(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("client_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def authenticate(request: Request) -> str:
    client_id = await verify_api_key(request)
    if client_id:
        return client_id

    client_id = verify_jwt(request)
    if client_id:
        return client_id

    raise HTTPException(status_code=401, detail="Authentication required (API key or JWT)")
