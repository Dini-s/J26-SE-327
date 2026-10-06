"""Redis Pub/Sub notifications for decayed trace links (the one real-time link to C3)."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

from agents.traceability_agent.config import DECAY_CHANNEL


class DecayEventPublisher:
    """Publishes ``trace_decayed`` JSON events so C3 can re-run its revalidation."""

    def __init__(
        self, client: Optional[Any] = None, channel: str = DECAY_CHANNEL, url: Optional[str] = None
    ) -> None:
        """Create the publisher.

        Args:
            client: A redis-py client (anything with ``publish(channel, message)``);
                created lazily from ``REDIS_URL`` if omitted.
            channel: Pub/Sub channel to publish on.
            url: Redis URL; defaults to ``REDIS_URL`` or ``redis://localhost:6379/0``.
        """
        load_dotenv()
        self._client = client
        self.channel = channel
        self._url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def client(self) -> Any:
        """The Redis client, created on first use (requires the ``redis`` package)."""
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(self._url)
        return self._client

    def publish(
        self,
        requirement_id: str,
        code_entity_id: str,
        previous_confidence: float,
        new_confidence: float,
    ) -> dict[str, Any]:
        """Publish a decay event.

        Args:
            requirement_id: Requirement whose link decayed.
            code_entity_id: The linked code entity.
            previous_confidence: Confidence before re-verification.
            new_confidence: Confidence after re-verification.

        Returns:
            The event that was published.
        """
        event = {
            "event": "trace_decayed",
            "requirementId": requirement_id,
            "codeEntityId": code_entity_id,
            "previousConfidence": previous_confidence,
            "newConfidence": new_confidence,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.client.publish(self.channel, json.dumps(event))
        return event
