import httpx
from fastapi import Request, Response
from app.config import UPSTREAM_URL

async def forward_request(request: Request) -> Response:
    async with httpx.AsyncClient() as client:
        url = f"{UPSTREAM_URL}{request.url.path}"

        upstream_response = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            params=request.query_params,
            content=await request.body(),
            timeout=10.0,
        )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=dict(upstream_response.headers),
    )