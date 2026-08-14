import time
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("gateway")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("gateway.log")
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        log_entry = {
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

        logger.info(json.dumps(log_entry))
        return response