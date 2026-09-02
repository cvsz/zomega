from redis import Redis
from fastapi import HTTPException
from .config import settings

redis = Redis.from_url(settings.redis_url, decode_responses=True)

def enforce(tenant_id: str):
    key = f"rate:{tenant_id}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = pipe.execute()
    if ttl == -1:
        redis.expire(key, 60)
    if int(count) > settings.omega_rate_limit_per_minute:
        raise HTTPException(429, "Rate limit exceeded")
