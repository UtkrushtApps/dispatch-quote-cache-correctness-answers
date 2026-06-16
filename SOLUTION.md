# Solution Steps

1. Identify the two bleed sources: the Redis key only used origin/destination even though EtaAgent and CapacityAgent depend on cargo_weight_kg and service_tier, and DispatchManager stored in-flight quote values in the manager-level _pending dictionary shared by all concurrent requests.

2. Replace the lane-only cache key with a stable request-safe key. Serialize the full QuoteRequest with sorted JSON, hash it, and use a versioned key such as dispatch:v2:{agent}:{request_hash}.

3. Store cached agent results in a small Redis envelope containing the agent name, the request fingerprint, and the AgentResult payload. On read, validate the envelope before returning it; delete invalid entries instead of using them.

4. Keep caching enabled with the existing TTL and cache only successful worker results, preserving the existing behavior for unavailable agents.

5. Add per-cache-key asyncio locks around cache misses. This prevents concurrent identical requests from stampeding the same worker while still allowing different agents and different requests to run concurrently.

6. Run the EtaAgent, CapacityAgent, and WeatherAgent memoized calls with asyncio.gather so the manager performs the read-only worker lookups concurrently.

7. Remove the request-shared _pending dictionary. Build a QuoteWorkingState inside build_quote for each request and pass that request-local state into _compute_price.

8. Preserve the response contract: copy origin, destination, and service_tier directly from the incoming request; set status to degraded and notes to {agent}_unavailable when any worker returns unavailable; leave price as None for degraded quotes.

9. Add correlation IDs to start, cache hit/miss/store, timeout/error, and completion logs so replayed concurrent requests can be traced independently.

10. Run Redis with docker compose and execute pytest to verify distinct requests produce distinct ETA/capacity values, concurrent mixed requests do not bleed, identical requests reuse cached worker results, and unavailable capacity keeps the degraded response shape.

