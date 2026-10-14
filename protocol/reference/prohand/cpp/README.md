# ProHand protocol reference client (C++)

The wire contract in one library: packed Cap'n Proto messages from the
public schema over ZeroMQ, with nothing of an application on top. Read it to
see exactly what crosses the socket; link it as is, or start your own client
from it.

Three classes, one per role:

| Class | Socket | What it carries |
|---|---|---|
| `ServiceClient` | REQ to the driver's command endpoint | ping, streaming mode, zero calibration, homing |
| `Publisher` | PUB to the hand and wrist streaming endpoints | joint and servo setpoints, latest-wins |
| `Subscriber` | SUB on the status endpoint | every status frame, with its header and host time |

Every message builder is also a plain `encode*` function returning the
packed bytes, for a program that brings its own transport.

## Build

Needs Cap'n Proto (library and the `capnp`, `capnpc-c++` tools) and
`cppzmq` with libzmq, from the system or from any CMake toolchain file:

```bash
brew install capnp zeromq cppzmq            # macOS
sudo apt install capnproto libcapnp-dev libzmq3-dev cppzmq-dev   # Debian, Ubuntu

cmake -S protocol/reference/prohand/cpp -B build
cmake --build build
./build/quickstart tcp://127.0.0.1
```

The schema is compiled at build time from `-DPROHAND_SCHEMA_DIR=…` when
given, else the monorepo's public edition under
`schemas/capnp/schema/prohand/public` when the package sits inside the
monorepo, else `protocol/schema/prohand` shipped beside the clients. Link the
`prohand_client` target from your own CMake project with `add_subdirectory`.

## Quickstart

`examples/quickstart.cpp` pings the driver, turns streaming on, sends one
open-hand command and prints status frames for three seconds. The left
hand's default TCP ports: 5562 commands, 5561 status, 5563 hand streaming,
5564 wrist streaming; the right hand's are 5572, 5571, 5573 and 5574.

```cpp
#include "prohand_client/prohand_client.hpp"
using namespace prohand_client;

ServiceClient service("tcp://127.0.0.1:5562");
service.connect();
service.ping();
service.setStreamingMode(true);

Publisher publisher("tcp://127.0.0.1:5563", "tcp://127.0.0.1:5564");
publisher.connect();
Subscriber subscriber("tcp://127.0.0.1:5561");
subscriber.connect();
FingerPose open;
for (const char *finger : kFingers) open[finger] = {0, 0, 0, 0};
for (;;) {
  auto status = subscriber.receive(200);
  if (!status) continue;
  if (status->which() == ::ProHandStatus::HAND_JOINT_STATUS) {
    auto joints = status->body().getHandJointStatus();
  }
  publisher.sendHandCommand(open, false, 0.3);
}
```

`Status::body()` is the Cap'n Proto reader for the frame and
`Status::which()` its variant; the public schema `prohand_sdk.capnp` lists
them all.

## Behaviour worth knowing

- A `ServiceClient` request the driver does not answer within its timeout
  returns `false` and reopens the socket, because a REQ socket waiting for a
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
- Velocities and the hand command's velocity saturation default to a moving
  value; the wire default of zero holds the hand still.

## Tests

```bash
ctest --test-dir build
```

`tests/decode_fixtures.cpp` decodes every public status variant from a
fixture the driver's own encoder wrote, and checks that this client's
encoders produce byte for byte what the Python reference client's do.
