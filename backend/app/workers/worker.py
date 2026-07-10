from __future__ import annotations

from redis import Redis
from rq import Connection, Worker

from app.core.config import settings


def main() -> None:
    connection = Redis.from_url(settings.redis_url)
    with Connection(connection):
        worker = Worker(["breachsim"])
        worker.work()


if __name__ == "__main__":
    main()
