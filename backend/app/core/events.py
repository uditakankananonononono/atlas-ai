import json
import os
from collections.abc import Callable
from redis import Redis

CHANNEL = "atlas:approval-events"

class RedisEventPublisher:
    """Cross-process approval event publisher backed by Redis Pub/Sub."""
    def __init__(self, url: str | None = None) -> None:
        self._redis = Redis.from_url(url or os.getenv("ATLAS_REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

    def publish(self, event: dict) -> None:
        self._redis.publish(CHANNEL, json.dumps(event, default=str))

    def listen(self, callback: Callable[[dict], None]) -> None:
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(CHANNEL)
        for message in pubsub.listen():
            callback(json.loads(message["data"]))
