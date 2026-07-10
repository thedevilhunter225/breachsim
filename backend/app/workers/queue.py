from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.config import settings


def get_queue(name: str = "breachsim") -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(name, connection=connection)
