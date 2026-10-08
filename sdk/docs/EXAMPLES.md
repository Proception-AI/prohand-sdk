# ProHand SDK Examples

Runnable snippets for the shipped SDKs. The package provides a **C** API
(`prohand_sdk.h`), a header-only **C++** wrapper (`ProHandClient.hpp`), and a
**Python** wrapper (`prohand_sdk`). All three are thin bindings over the same
library, so the concepts map one-to-one.

Every example assumes the IPC host (driver) is already running — see the package
`README.md`. The driver owns the `/tmp/prohand-*.ipc` sockets these clients
connect to; nothing works without it.

For complete, tested programs see `sdk/demo/` — `demo/python/src/prohand_demo/`
and `demo/cpp/src/`. Those are the reference implementations and are kept in sync
with the library.

## Table of Contents

- [Setup and Connection](#setup-and-connection)
- [Basic Commands](#basic-commands)
- [Hand Control](#hand-control)
- [Wrist Control](#wrist-control)
- [Streaming Mode](#streaming-mode)
- [Calibration and Homing](#calibration-and-homing)
- [Status Monitoring](#status-monitoring)
- [Liveness](#liveness)
- [Low-Level Actuator Control](#low-level-actuator-control)
- [Error Handling](#error-handling)
- [Tips and Best Practices](#tips-and-best-practices)
- [Troubleshooting](#troubleshooting)

______________________________________________________________________

## Setup and Connection

The client takes four endpoints, in this order: command, status, hand streaming,
wrist streaming.

### Python

```python
from prohand_sdk import ProHandClient, get_version, discover_usb_devices

print("SDK version:", get_version())
for dev in discover_usb_devices():
    print("found:", dev.port_name, dev.display_name)

client = ProHandClient(
    "ipc:///tmp/prohand-commands.ipc",
    "ipc:///tmp/prohand-status.ipc",
    "ipc:///tmp/prohand-hand-streaming.ipc",
    "ipc:///tmp/prohand-wrist-streaming.ipc",
)

client.send_ping()
print("connected:", client.is_connected())
client.close()
```

`ProHandClient` is also a context manager, which is the preferred form:

```python
with ProHandClient(cmd, status, hand_stream, wrist_stream) as client:
    client.send_ping()
```

### C++

```cpp
#include <prohand_sdk/ProHandClient.hpp>
#include <iostream>

int main() {
  using namespace prohand_sdk;
  ProHandClient client("ipc:///tmp/prohand-commands.ipc",
                       "ipc:///tmp/prohand-status.ipc",
                       "ipc:///tmp/prohand-hand-streaming.ipc",
                       "ipc:///tmp/prohand-wrist-streaming.ipc");

  client.sendPing();
  std::cout << "connected: " << client.isConnected() << "\n";
  return 0;
}
```

The wrapper is RAII — the handle is released when `client` goes out of scope.
Failures throw `SdkException`.

### C

```c
#include <prohand_sdk/prohand_sdk.h>
#include <stdio.h>

int main(void) {
  ProHandClientHandle *client = prohand_client_create(
      "ipc:///tmp/prohand-commands.ipc", "ipc:///tmp/prohand-status.ipc",
      "ipc:///tmp/prohand-hand-streaming.ipc",
      "ipc:///tmp/prohand-wrist-streaming.ipc");
  if (!client) {
    fprintf(stderr, "failed to create client\n");
    return 1;
  }

  prohand_send_ping(client);
  printf("connected: %d\n", prohand_client_is_connected(client));
  prohand_client_destroy(client);
  return 0;
}
```

Every C function returns `ProHandResult` (`PROHAND_SUCCESS == 0`) unless
documented otherwise. Always check it.

______________________________________________________________________

## Basic Commands

### Ping

```python
client.send_ping()
```

### Enable streaming mode

The driver must be in streaming mode before the streaming channels accept
commands. `wait_for_streaming_ready()` retries and confirms the device reached the
Running state.

```python
client.set_streaming_mode(True)
if not client.wait_for_streaming_ready(timeout=10.0):
    raise RuntimeError("driver never reached Running state")
```

______________________________________________________________________

## Hand Control

Finger poses are **20 joint angles in radians**, ordered
`thumb[0..3], index[4..7], middle[8..11], ring[12..15], pinky[16..19]`, and each
finger's four joints are `[Abd, MCP, PIP, DIP]`.

Joint space is **anatomical and identical for left and right hands** — positive
abduction splays a finger toward the thumb on either one. Handedness is resolved
by the device's actuator wiring, so you send the same numbers regardless of which
hand is attached.

```python
import math

positions = [0.0] * 20
# Curl the index finger: MCP 45 deg, PIP 40 deg, DIP 30 deg.
positions[5] = math.radians(45.0)
positions[6] = math.radians(40.0)
positions[7] = math.radians(30.0)

client.send_hand_command(positions, torque=0.45, velocity_saturation=0.2)
```

**`torque`** is normalized `0.0`-`1.0` and accepts three shapes. The wire carries
one value per joint, so per-finger control has always been possible on the
hardware — the SDK simply did not expose it before:

```python
client.send_hand_command(positions, 0.45)                        # whole hand
client.send_hand_command(positions, [0.2, 0.6, .45, .45, .45])   # per finger
client.send_hand_command(positions, [...20 values...])           # per joint
```

Per-finger order is thumb, index, middle, ring, pinky. Per-joint order matches
`positions`.

**`velocity_saturation`** caps servo speed for every finger in the command,
normalized `0.0`-`1.0`. `0.0` means "use the firmware default". It is per-hand:
the wire carries a single value for all fingers, so it cannot be set per finger.

It is a *cap*, not a target. A trajectory asking for more travel per unit time
than the cap allows gets truncated rather than tracked — 80 deg of travel in
0.5 s needs 160 deg/s and cannot be followed at any setting. Either lengthen the
motion or raise the cap.

C++ takes a scalar or a vector; C takes the 20-value array directly:

```cpp
std::vector<float> positions(20, 0.0f);
positions[5] = 0.785f;                              // index MCP, radians
client.sendHandCommands(positions, 0.45f, 0.2f);    // uniform
client.sendHandCommands(positions, {0.2f, 0.6f, 0.45f, 0.45f, 0.45f});  // per finger
```

```c
float positions[20] = {0};
float torques[20];
for (int i = 0; i < 20; i++) torques[i] = 0.45f;
positions[5] = 0.785f;
prohand_send_hand_command(client, positions, torques, 0.2f);
```

______________________________________________________________________

## Wrist Control

The wrist is two joints, `[Yaw, Pitch]`, in radians.

```python
client.send_wrist_command([math.radians(15.0), 0.0])
```

`use_profiler=True` routes the target through the SDK's motion profiler, which
smooths it against configured velocity/acceleration/jerk limits. The profiler is
present only when the library was built with the `motion-profiler` feature;
`set_wrist_limits` returns `PROHAND_ERROR_UNSUPPORTED` otherwise.

```python
client.set_wrist_limits(
    max_velocity=[1.0, 1.0],        # rad/s
    max_acceleration=[5.0, 5.0],    # rad/s^2
    max_jerk=[50.0, 50.0],          # rad/s^3
)
client.send_wrist_command([math.radians(15.0), 0.0], use_profiler=True)
```

______________________________________________________________________

## Streaming Mode

Use the streaming channel for continuous control. It is lower latency than the
command channel and drops stale frames instead of round-tripping per message, so
a slow consumer never backs you up.

```python
import time

client.set_streaming_mode(True)
client.wait_for_streaming_ready(timeout=10.0)

positions = [0.0] * 20
t0 = time.monotonic()
while time.monotonic() - t0 < 5.0:
    phase = math.sin((time.monotonic() - t0) * 2.0)
    for finger in range(1, 5):                     # index..pinky
        positions[finger * 4 + 1] = math.radians(40.0) * (0.5 + 0.5 * phase)
    client.send_hand_streams(positions, 0.45, 50)
    client.send_wrist_streams([0.0, 0.0])
    time.sleep(0.02)                               # 50 Hz

client.set_streaming_mode(False)
```

Both channels carry the same joint-space commands and the device runs the
kinematics either way; only the transport differs.

______________________________________________________________________

## Calibration and Homing

These move the hand. **Keep it clear of obstructions.**

### Zero calibration

Sets the current position of the selected servos as their zero. The mask has 16
entries, one per servo.

```python
mask = [False] * 16
mask[3] = True
client.send_zero_calibration(mask)
```

### Auto-calibration

Drives the selected fingers against their hard stops to discover their range.
Progress is reported on the status channel.

```python
from prohand_sdk import CalibrationMask

client.send_auto_calibration(CalibrationMask.ALL)
client.send_auto_calibration(CalibrationMask.THUMB | CalibrationMask.INDEX)
client.send_auto_calibration(CalibrationMask.ABORT)   # stop a running pass
```

In C, use the `PROHAND_CALIB_*` macros:

```c
prohand_send_auto_calibration(client, PROHAND_CALIB_THUMB | PROHAND_CALIB_INDEX);
prohand_send_auto_calibration(client, PROHAND_CALIB_ABORT);
```

### Homing

```python
client.send_homing(True)    # start
client.send_homing(False)   # abort
```

______________________________________________________________________

## Status Monitoring

`try_recv_status()` is non-blocking and returns `None` when nothing is queued.

```python
status = client.try_recv_status()
if status is not None and status.is_valid:
    if status.status_type == 1:
        print("rotary positions:", status.rotary_positions)
    elif status.status_type == 2:
        print("linear positions:", status.linear_positions)
    elif status.status_type == 3:
        print("rotary targets:", status.rotary_targets)
    elif status.status_type == 4:
        print("linear targets:", status.linear_targets)
```

`status_type` values: `0` other, `1` rotary status, `2` linear status, `3` rotary
target echo, `4` linear target echo. Only the array matching `status_type` carries
fresh data on a given read.

**Units.** Positions are raw `int16` in centidegrees (0.01 deg per count), so
divide by 100 for degrees. The C++ wrapper converts to radians for you and exposes
`rotaryPositions`, `linearPositions`, `rotaryTargets`, `linearTargets`.

Poll in a loop rather than once — status arrives at up to 200 Hz, and a single call
sees only what is currently queued.

```python
import time

deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    status = client.try_recv_status()
    if status is None:
        time.sleep(0.005)
        continue
    if status.status_type == 1:
        degrees = [p / 100.0 for p in status.rotary_positions]
        print(degrees[:4])
```

______________________________________________________________________

## Liveness

`is_connected()` stays true for up to 10 seconds after the driver goes quiet,
which is too coarse for a control loop. `ms_since_last_heartbeat()` reports the age
of the last status message instead.

```python
if client.ms_since_last_heartbeat() > 500:
    # Driver has gone silent — stop commanding motion.
    client.set_streaming_mode(False)
```

The counter is seeded when the client is created, so treat it as meaningful only
after the first successful `try_recv_status()`.

______________________________________________________________________

## Low-Level Actuator Control

Prefer joint-space commands. The device converts them using its own wiring map,
which is the only place that knows the hand's handedness and hardware variant.
Actuator-space commands bypass that, making **you** responsible for the mapping —
and a map that does not match the attached hand drives the wrong tendons.

Use these only for servo-level bring-up and diagnostics.

```python
positions = [0.0] * 16          # radians, indexed by servo bus ID
torques = [0.3] * 16            # normalized 0.0 - 1.0
client.send_rotary_commands(positions, torques)

client.send_linear_commands([0.0, 0.0], [0.3, 0.3])   # 2 linear actuators
```

______________________________________________________________________

## Error Handling

Python raises on failure; the hierarchy is `ProHandError` with `ConnectionError`
and `InvalidArgumentError` subclasses.

```python
from prohand_sdk import ProHandError, ConnectionError, InvalidArgumentError

try:
    client.send_hand_command(positions, 0.45, 50)
except InvalidArgumentError as e:
    print("bad arguments:", e)          # wrong list length, velocity > 255
except ConnectionError as e:
    print("not connected:", e)
except ProHandError as e:
    print("sdk error:", e)
```

C++ throws `SdkException`. C returns `ProHandResult`:

| Code | Meaning |
|---|---|
| `PROHAND_SUCCESS` | success (0) |
| `PROHAND_ERROR_NULL` | null handle or argument |
| `PROHAND_ERROR_CONNECTION` | transport failure |
| `PROHAND_ERROR_INVALID_ARGUMENT` | bad argument |
| `PROHAND_ERROR_NOT_CONNECTED` | streaming not available |
| `PROHAND_ERROR_UNSUPPORTED` | feature absent from this build |
| `PROHAND_ERROR_OTHER` | unspecified |

### Retrying a connection

```python
import time

def connect(retries=5, delay=1.0):
    for attempt in range(retries):
        try:
            client = ProHandClient(cmd, status, hand_stream, wrist_stream)
            client.send_ping()
            return client
        except ProHandError as e:
            print(f"attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    raise RuntimeError("could not connect to the IPC host")
```

Note that creating a client succeeds even with no driver running — the transport
connects lazily. Send a ping and check `is_connected()` to confirm a live link.

______________________________________________________________________

## Tips and Best Practices

- Send joint-space commands and let the device do the kinematics.
- Pass a non-zero `velocity_saturation` when speed matters; `0` works but means
  "whatever the default is".
- Size motion to the servo envelope: 50 deg/s default, 110 deg/s maximum.
- Stream at a steady rate (50 Hz is a good default) rather than in bursts.
- Poll status in a loop; one `try_recv_status()` sees only what is queued.
- Watch `ms_since_last_heartbeat()` in any loop that commands motion.
- Close the client explicitly, or use the context manager.

______________________________________________________________________

## Troubleshooting

### Nothing moves, but every call returns success

Usually the driver is not actually talking to a hand, or streaming mode was never
enabled. Check, in order:

1. Is the driver running, and did it claim the USB device? A second driver holding
   the device makes the first fail with an access error while its sockets still
   bind — so a client connects happily to a driver with no hand behind it.
1. Do your endpoints match the driver's? A driver started with a node prefix binds
   e.g. `/tmp/right-commands.ipc`, not `/tmp/prohand-commands.ipc`.
1. Did `wait_for_streaming_ready()` return `True`?
1. Is the motion inside the servo envelope? See `velocity_saturation` above.

### Connection issues

- Confirm the socket files exist for the endpoints you passed.
- Remove stale socket files left behind by a driver that was killed.
- For TCP endpoints, confirm host, port and firewall.

### Poor tracking or jerky motion

Usually a velocity cap too low for the commanded trajectory, or an irregular send
rate. Raise `velocity_saturation`, lengthen the motion, or stabilise your loop
period.

______________________________________________________________________

For the message-level protocol see [API.md](API.md). For complete working programs
see `sdk/demo/`.
