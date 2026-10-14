"""Connect to a running ProHand driver, ping it, turn streaming on, send one
open-hand command, and print the status frames that come back.

    python -m prohand_client [tcp://127.0.0.1]

The left hand's default TCP ports: 5562 commands (REQ/REP), 5561 status
(PUB/SUB), 5563 hand streaming and 5564 wrist streaming (PUB/SUB); the right
hand's are 5572, 5571, 5573 and 5574.
"""

from __future__ import annotations

import sys
import time

from prohand_client import FINGERS, Publisher, ServiceClient, Subscriber


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "tcp://127.0.0.1"

    service = ServiceClient(f"{host}:5562").connect()
    if not service.ping():
        print("no reply from the driver within 1 s", file=sys.stderr)
        return 1
    print("driver answered the ping")

    subscriber = Subscriber(f"{host}:5561").connect()
    publisher = Publisher(f"{host}:5563", f"{host}:5564").connect()

    if not service.set_streaming_mode(True):
        print(
            "the driver did not acknowledge streaming mode within 1 s", file=sys.stderr
        )
        return 1
    # The first status frame shows the subscriptions are up; a setpoint sent
    # before that is dropped by the PUB socket. Streaming is a stream: the
    # setpoint goes out on every pass, not once.
    open_hand = {finger: [0.0] * 4 for finger in FINGERS}
    until = time.monotonic() + 3.0
    frames = 0
    while time.monotonic() < until:
        status = subscriber.receive(200)
        if status is None:
            continue
        publisher.send_hand_command(open_hand, torque=0.3)
        frames += 1
        if frames % 50 == 1:
            print(
                f"seq {status.header.seq} device {status.header.t_device_us} us "
                f"host {status.t_host_us} us: {status.which}"
            )
    print(f"{frames} status frames in 3 s")

    service.set_streaming_mode(False)
    publisher.disconnect()
    subscriber.disconnect()
    service.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
