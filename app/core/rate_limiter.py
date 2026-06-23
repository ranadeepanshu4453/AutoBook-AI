"""
app/core/rate_limiter.py
────────────────────────────────────────────────────
IP-based rate limiter backed by MongoDB.

Limits (per IP):
  - 60 requests / minute
  - 3600 requests / hour

Uses upsert + $inc for atomic increments.
TTL indexes on `expires_at` auto-delete expired windows.

Two documents per active IP (one per window):
  key = "ip:<ip>:minute:<YYYY-MM-DDTHH:MM>"
  key = "ip:<ip>:hour:<YYYY-MM-DDTHH>"
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.core.logger import logger
from app.db.mongo import mongo_db

COLLECTION = "rate_limit_counters"

# ── Limits ────────────────────────────────────────────────────────────────────
MINUTE_LIMIT = 60
HOUR_LIMIT   = 3600

# ── Window helpers ────────────────────────────────────────────────────────────

def _windows(ip: str) -> list[dict]:
    """
    Return the two window descriptors for this IP.
    Each descriptor carries everything needed for one upsert.
    """
    now = datetime.now(timezone.utc)

    minute_key  = f"ip:{ip}:minute:{now.strftime('%Y-%m-%dT%H:%M')}"
    minute_exp  = now.replace(second=0, microsecond=0) + timedelta(minutes=2)

    hour_key    = f"ip:{ip}:hour:{now.strftime('%Y-%m-%dT%H')}"
    hour_exp    = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    return [
        {
            "key":        minute_key,
            "ip":         ip,
            "window":     "minute",
            "limit":      MINUTE_LIMIT,
            "expires_at": minute_exp,
            "retry_after": 60,
        },
        {
            "key":        hour_key,
            "ip":         ip,
            "window":     "hour",
            "limit":      HOUR_LIMIT,
            "expires_at": hour_exp,
            "retry_after": 3600,
        },
    ]


# ── Public API ────────────────────────────────────────────────────────────────

class RateLimiter:

    async def check(self, ip: str) -> tuple[bool, int, str]:
        """
        Atomically increment counters for both windows and check limits.

        Returns:
            (allowed, retry_after, window)
            allowed      — True if request should proceed
            retry_after  — seconds until window resets (only meaningful when blocked)
            window       — "minute" | "hour" (which limit was hit)
        """
        for window in _windows(ip):
            try:
                result = await mongo_db.update_one(
                    collection=COLLECTION,
                    query={"key": window["key"]},
                    update={
                        "$inc": {"count": 1},
                        "$setOnInsert": {
                            "key":        window["key"],
                            "ip":         window["ip"],
                            "window":     window["window"],
                            "expires_at": window["expires_at"],
                        },
                    },
                    upsert=True,
                )

                # Read back the current count
                doc = await mongo_db.find_one(COLLECTION, {"key": window["key"]})
                count = doc["count"] if doc else 1

                if count > window["limit"]:
                    logger.warning(
                        f"[RateLimit] {window['window']} limit hit — "
                        f"IP: {ip} | count: {count}/{window['limit']}"
                    )
                    return False, window["retry_after"], window["window"]

            except Exception as e:
                # Never block a request because of a limiter failure
                logger.error(f"[RateLimit] Counter update failed for {ip}: {e}")
                return True, 0, ""

        return True, 0, ""

    async def create_indexes(self) -> None:
        try:
            await mongo_db.create_rate_limiting_index(
                COLLECTION, [("expires_at", 1)],
                expire_after_seconds=0,  
            )
            await mongo_db.create_rate_limiting_index(
                COLLECTION, [("key", 1)],
                unique=True,
            )
            logger.info("[RateLimit] MongoDB indexes created")
        except Exception as e:
            logger.warning(f"[RateLimit] Index creation warning: {e}")


rate_limiter = RateLimiter()