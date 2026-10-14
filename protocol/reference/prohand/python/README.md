# ProHand protocol reference client (Python)

The wire contract in one file: packed Cap'n Proto messages from the public
schema over ZeroMQ, with nothing of an application on top. Read it to see
exactly what crosses the socket; use it as is, or as the starting point of
your own client.

Three classes, one per role:

| Class | Socket | What it carries |
|---|---|---|
| `ServiceClient` | REQ to the driver's command endpoint | ping, streaming mode, zero calibration, homing |
| `Publisher` | PUB to the hand and wrist streaming endpoints | joint and servo setpoints, latest-wins |
| `Subscriber` | SUB on the status endpoint | every status frame, with its header and host time |

Every message builder is also a plain `encode_*` function returning the
packed bytes, for a program that brings its own transport.

## Install

```bash
pip install -e protocol/reference/prohand/python
```

The schema is loaded at import from `PROHAND_SCHEMA_DIR` when set, else the
monorepo's public edition under `schemas/capnp/schema/prohand/public` when
the package sits inside the monorepo, else `protocol/schema/prohand` shipped
beside the clients.

## Quickstart

```bash
python -m prohand_client tcp://127.0.0.1
```

pings the driver, turns streaming on, sends one open-hand command and prints
status frames for three seconds. The left hand's default TCP ports: 5562
commands, 5561 status, 5563 hand streaming, 5564 wrist streaming; the right
hand's are 5572, 5571, 5573 and 5574.

```python
from prohand_client import FINGERS, Publisher, ServiceClient, Subscriber

service = ServiceClient("tcp://127.0.0.1:5562").connect()
service.ping()
service.set_streaming_mode(True)

publisher = Publisher("tcp://127.0.0.1:5563", "tcp://127.0.0.1:5564").connect()
subscriber = Subscriber("tcp://127.0.0.1:5561").connect()
while True:
    status = subscriber.receive(timeout_ms=200)
    if status is None:
        continue
    print(status.header.seq, status.t_host_us, status.which)
    if status.which == "handJointStatus":
        joints = status.body.handJointStatus
    publisher.send_hand_command({finger: [0.0] * 4 for finger in FINGERS}, torque=0.3)
```

`Status.body` is the Cap'n Proto reader for the frame; `Status.which` names
the variant, and the public schema `prohand_sdk.capnp` lists them all.

## Behaviour worth knowing

- A `ServiceClient` request the driver does not answer within its timeout
  returns `False` and reopens the socket, because a REQ socket waiting for a
  reply accepts no further request.
- A `Publisher` keeps one pending frame per socket (`CONFLATE`): a driver
  that stalls gets the newest setpoint when it resumes, never a backlog. A
  PUB socket never reports what a peer received, so send the setpoint on
  every control pass, and only after the first status frame has arrived.
- Wire integers follow one rule in all three reference clients: clamp to
  the field's range, never wrap an angle, round half away from zero.
- A `Publisher` whose `inproc://` peer was never bound makes libzmq 4.3.5
  assert at context teardown (`ctx.cpp:789`, a CONFLATE socket with a
  pending inproc connection). Bind every inproc peer in a test; TCP and
  ipc endpoints are unaffected.
- A `Subscriber` keeps a short receive buffer so a slow reader sees recent
  frames, and reopens its socket after five seconds of silence, since a SUB
  socket is never told that its publisher went away.
- Velocities and the hand command's `velocity_saturation` default to a
  moving value; the wire default of zero holds the hand still.

## Tests

```bash
uv run pytest
```

`tests/test_contract.py` decodes every public status variant from a fixture
the driver's own encoder wrote, and keeps a fixture of every command this
client builds for the driver's tests to decode.
