import logging

from redis import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)

redis_client = Redis.from_url(
    get_settings().redis_url,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def check_redis() -> bool:
    try:
        return bool(redis_client.ping())
    except Exception:
        logger.exception("Redis health check failed")
        return False
