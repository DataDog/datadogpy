import pytest

from datadog.dogstatsd.base import DogStatsd
from tests.unit.dogstatsd.test_statsd import FakeSocket


@pytest.mark.parametrize("aggregate", [False, True])
@pytest.mark.parametrize("method,args", [
    ("gauge", ("metric", 1)),
    ("count", ("metric", 1)),
    ("histogram", ("metric", 1)),
    ("distribution", ("metric", 1)),
    ("timing", ("metric", 1)),
    ("event", ("title", "text")),
    ("service_check", ("service", 0)),
])
@pytest.mark.parametrize("default,override,expected", [
    (None, "bogus", None),
    ("bogus", None, None),
    ("low", "bogus", "low"),
    ("bogus", "high", "high"),
    ("low", "none", "none"),
])
def test_cardinality_fallback_packets(aggregate, method, args, default, override, expected):
    client = DogStatsd(
        disable_aggregation=not aggregate,
        disable_telemetry=True,
        origin_detection_enabled=False,
        flush_interval=10000,
        max_metric_samples_per_context=10,
        cardinality=default,
    )
    client.socket = FakeSocket()
    try:
        getattr(client, method)(*args, cardinality=override)
        if aggregate:
            client.flush_aggregated_metrics()
        packet = client.socket.recv(no_wait=True)
        assert packet is not None
        if expected is None:
            assert "|card:" not in packet
        else:
            assert "|card:{}".format(expected) in packet
        assert "bogus" not in packet
    finally:
        client.stop()
