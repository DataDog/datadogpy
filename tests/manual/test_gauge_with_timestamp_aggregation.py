import time

from datadog.dogstatsd.base import DogStatsd

client = DogStatsd(
    socket_path="/tmp/dsd.sock",
    disable_aggregation=True,
    disable_buffering=False,
    flush_interval=1.0,
    disable_telemetry=True,
)

start = time.time()
i = 0

while time.time() - start < 10:
    i += 1
    client.gauge_with_timestamp("test.aggregation", float(i), tags=["env:test"], timestamp=time.time())

client.stop()
print("Done.")

