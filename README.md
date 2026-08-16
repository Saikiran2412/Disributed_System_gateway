Distributed Rate Limiter & API Gateway

A standalone API gateway built with FastAPI that sits in front of a backend service (a Smart Router Chatbot), handling authentication, distributed rate limiting, circuit breaking, and structured logging — the cross-cutting concerns a real gateway (Kong, Traefik, AWS API Gateway) handles in production.

Why this project exists

Most fresher portfolios show CRUD apps. This project demonstrates distributed systems concepts that are hard to fake: atomic operations under concurrency, shared state across instances, graceful degradation under failure, and defense-in-depth request handling. Every component here was built, broken, debugged, and re-verified against real failures — not just written once and assumed correct.

Architecture
Client → Gateway (port 9000) → Auth → Rate Limiter → Circuit Breaker → Proxy → Upstream (port 8000)
                                   ↓          ↓              ↓
                                 Redis      Redis          Redis
                          (shared state across all gateway instances)

The gateway is the single entry point. It never runs the actual business logic — it controls access to the backend service, exactly like a receptionist controls access to a building without doing the work happening inside.

Components
1. Proxy layer (app/proxy.py)

A catch-all route (/{path:path}) that forwards any incoming request to the upstream service using httpx.AsyncClient, preserving method, headers, body, and query params, then relays the response back unchanged.

Why httpx.AsyncClient and not requests: a synchronous client would block the event loop while waiting on the upstream, meaning the gateway couldn't handle any other incoming request during that wait. Since the gateway sits in the path of every request to every service, a blocking call here would make the gateway itself the bottleneck.

2. Rate limiting — two algorithms, both implemented (app/rate_limiter.py, app/sliding_window.py)

Token Bucket: each client has a bucket holding N tokens that refill at a fixed rate. Allows bursts up to the bucket size, capped by the refill rate long-term. Used by Stripe, AWS, and most production APIs because it feels natural — occasional bursts are fine, sustained abuse isn't.

Sliding Window Counter: tracks request counts in fixed time buckets and computes a weighted average between the current and previous bucket to approximate a true rolling window. More precise/fair (no reset-cliff at window boundaries) than a naive fixed window, and far cheaper than storing every individual timestamp (sliding window log).

Both are selectable per-request via the X-RateLimit-Algorithm header (token_bucket or sliding_window), so the two can be directly compared.

The core distributed systems problem this solves: with multiple gateway instances behind a load balancer, an in-memory counter breaks — two instances could each independently allow a request past the same "4 of 5 used" state, since neither knows what the other just did. This is a race condition. The fix: store state in Redis (shared across all instances) and execute the entire "read → compute → write" sequence as a single atomic Lua script, so no other instance's check can interleave in the middle of it.

3. Authentication (app/auth.py)

Supports two methods, tried in order:

API Key — X-API-Key header, checked against a Redis hash (api_keys). Simple, requires a lookup, instantly revocable (just delete the key from the store).
JWT — Authorization: Bearer <token> header, verified via signature (HS256) against a shared secret. Self-contained (no DB lookup needed to verify), but not instantly revocable — a token is valid until it naturally expires unless a separate blocklist is maintained.
4. Circuit breaker (app/circuit_breaker.py)

Protects the gateway (and the struggling upstream) from cascading failure. Three states, all persisted in Redis so they're shared across gateway instances:

Closed — normal operation, requests flow through, failures are counted.
Open — after FAILURE_THRESHOLD consecutive failures, the breaker trips. For COOLDOWN_SECONDS, every request is rejected immediately with a 503 — no attempt is even made to reach the dead upstream.
Half-open — once cooldown passes, exactly one request is let through as a test. Success flips the breaker back to closed; failure reopens it and resets the cooldown.

Why this matters: without it, every request to a dead upstream hangs on a real connection attempt/timeout (slow failure, wasted resources, and can push a struggling-but-alive service into fully dead). The circuit breaker fails fast instead, protecting both the client's experience and the recovering service.

5. Structured logging (app/logging_middleware.py)

Every request produces one JSON log line (method, path, client IP, status code, duration) via FastAPI/Starlette middleware — regardless of which route or outcome. Designed for machine parsing (log aggregators like Datadog, ELK, Loki), not just human reading in a terminal.

Tech stack
FastAPI — async control plane
Redis — shared state for rate limits, circuit breaker, API keys (with AOF persistence enabled so data survives container restarts)
httpx — async upstream calls
PyJWT — JWT signing/verification
Docker — Redis container
uv — Python package management
Running it
powershell
# 1. Start Redis (with persistence)
docker run -d --name gateway-redis --restart unless-stopped -p 6379:6379 -v gateway-redis-data:/data redis:7-alpine redis-server --appendonly yes

# 2. Seed test API keys
docker exec -it gateway-redis redis-cli
HSET api_keys sk_test_alice client_id:alice
exit

# 3. Start the upstream service (Smart Router Chatbot) on port 8000

# 4. Start the gateway
uv run uvicorn app.main:app --reload --port 9000
Testing each component

Proxy + rate limit (token bucket):

powershell
Invoke-RestMethod -Uri "http://localhost:9000/chat" -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="sk_test_alice"} -Body '{"query": "hello"}'

Sliding window instead:

powershell
Invoke-RestMethod -Uri "http://localhost:9000/chat" -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="sk_test_alice"; "X-RateLimit-Algorithm"="sliding_window"} -Body '{"query": "hello"}'

Circuit breaker — stop the upstream, then fire several requests in a row; watch 502 (real failures) turn into 503 (fast-fail once tripped) after the failure threshold is hit.

Known limitations / what I'd do differently at scale
API keys and rate-limit state share one Redis instance. In production I'd split them: rate-limit/circuit-breaker state is ephemeral (safe to lose on restart), while API keys are closer to real application data and belong in a database or a separately-persisted store.
IP-based fallback identity isn't used — client identity always comes from a verified API key or JWT, deliberately, since IP-based limiting is weak (shared IPs, proxies, VPNs all break it).
No distributed tracing — logs are structured per-request but not correlated across the auth → rate-limit → circuit-breaker → proxy chain with a trace ID. A production version would add a request ID propagated through every log line.
Circuit breaker is per-service, not per-endpoint. A more granular breaker could isolate failures to a specific route rather than tripping the whole upstream.
