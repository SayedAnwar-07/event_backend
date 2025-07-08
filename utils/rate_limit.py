from django.core.cache import cache
from datetime import datetime, timedelta

def check_rate_limit(key: str, limit: int, period: int):

    cache_key = f"rate-limit:{key}"
    attempts = cache.get(cache_key, [])

    # Remove expired timestamps
    now = datetime.now()
    valid_attempts = [ts for ts in attempts if now - ts < timedelta(seconds=period)]

    if len(valid_attempts) >= limit:
        return False

    # Add current attempt and save
    valid_attempts.append(now)
    cache.set(cache_key, valid_attempts, timeout=period)
    return True
