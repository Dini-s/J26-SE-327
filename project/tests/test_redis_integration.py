"""Real Redis pub/sub (skipped automatically when no Redis server is reachable)."""

import json
import threading
import time

import pytest

from agents.traceability_agent.events import DecayEventPublisher

redis = pytest.importorskip("redis")


@pytest.fixture
def server():
    client = redis.Redis(socket_connect_timeout=1)
    try:
        client.ping()
    except Exception:
        pytest.skip("no Redis server on localhost:6379")
    return client


def test_decay_event_is_delivered_to_a_real_subscriber(server):
    channel = "trace_decayed_test_" + str(time.time_ns())
    received = []
    ready = threading.Event()

    def listen():
        pubsub = server.pubsub()
        pubsub.subscribe(channel)
        ready.set()
        for message in pubsub.listen():
            if message["type"] == "message":
                received.append(json.loads(message["data"]))
                return

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    assert ready.wait(2)
    time.sleep(0.3)
    sent = DecayEventPublisher(channel=channel).publish("REQ-091", "pricing/discount.py", 0.88, 0.41)
    thread.join(timeout=3)
    assert received == [sent]
    assert set(sent) == {"event", "requirementId", "codeEntityId", "previousConfidence", "newConfidence", "timestamp"}
