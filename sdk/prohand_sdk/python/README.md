# ProHand SDK - Python Client

Python bindings for the ProHand robotic hand control system.

## Installation

### Option 1: pip install (recommended)

```bash
cd prohand_sdk/python
pip install -e .
```

### Option 2: Direct import

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/prohand_sdk/python"
```

## Quick Start

```python
from prohand_sdk import ProHandClient, discover_usb_devices, get_version

# Check version
print(f"SDK Version: {get_version()}")

# Discover connected devices
devices = discover_usb_devices()
for device in devices:
    print(f"Found: {device.display_name}")

# Connect to device
with ProHandClient(
    "tcp://127.0.0.1:5562",  # Command endpoint
    "tcp://127.0.0.1:5561",  # Status endpoint
    "tcp://127.0.0.1:5563",  # Hand streaming endpoint
    "tcp://127.0.0.1:5564"   # Wrist streaming endpoint
) as client:
    # Send commands
    client.send_ping()

    # Control joints
    positions = [0.0] * 16  # Radians
    torques = [0.45] * 16   # Normalized 0.0-1.0
    client.send_rotary_commands(positions, torques)

    # Poll status
    status = client.try_recv_status()
    if status:
        print(f"Positions: {status.rotary_positions}")
```

## API Reference

### ProHandClient

Main client for controlling the ProHand device.

#### `__init__(command_endpoint: str, status_endpoint: str, hand_streaming_endpoint: str, wrist_streaming_endpoint: str)`

Create a new client connection.

**Parameters:**

- `command_endpoint`: ZeroMQ endpoint for commands (e.g., "tcp://127.0.0.1:5562")
- `status_endpoint`: ZeroMQ endpoint for status (e.g., "tcp://127.0.0.1:5561")
- `hand_streaming_endpoint`: ZeroMQ endpoint for hand streaming (e.g., "tcp://127.0.0.1:5563")
- `wrist_streaming_endpoint`: ZeroMQ endpoint for wrist streaming (e.g., "tcp://127.0.0.1:5564")

#### `send_ping() -> None`

Send a ping command to the device.

#### `set_streaming_mode(enabled: bool) -> None`

Enable or disable high-frequency streaming mode.

#### `send_rotary_commands(positions: List[float], torques: List[float]) -> None`

Control the 16 finger joints.

**Parameters:**

- `positions`: List of 16 joint positions in radians
- `torques`: List of 16 torque values (0.0 to 1.0)

#### `send_linear_commands(positions: List[float], speeds: List[float]) -> None`

Control the 2 wrist motors (low-level actuator control).

**Parameters:**

- `positions`: List of 2 positions in radians
- `speeds`: List of 2 speed values (0.0 to 1.0)

#### `send_wrist_command(positions: List[float], use_profiler: bool = False) -> None`

Control the 2 wrist joints (high-level joint control with inverse kinematics).

**Parameters:**

- `positions`: List of 2 wrist joint angles in radians
- `use_profiler`: Whether to enable wrist motion profiling (position-only, implicit max velocity)

**Note:** This is the high-level API that uses inverse kinematics. For low-level actuator control, use `send_linear_commands()`.

#### `send_wrist_streams(positions: List[float], use_profiler: bool = False) -> None`

Control the 2 wrist joints via streaming channel (high-frequency, requires streaming mode).

**Parameters:**

- `positions`: List of 2 wrist joint angles in radians
- `use_profiler`: Whether to enable wrist motion profiling (position-only, implicit max velocity)

**Requires:** Client created with streaming endpoint AND driver in streaming mode.

#### `send_hand_command(positions, torque=0.45, velocity_saturation=0.0) -> None`

Control all 20 finger joints (high-level joint control with inverse kinematics).

**Parameters:**

- `positions`: List of 20 joint angles in radians (5 fingers × 4 joints)
  - Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
- `torque`: Normalized 0.0 to 1.0. A scalar applies to the whole hand, 5 values
  apply per finger (thumb to pinky), and 20 apply per joint, in the same order
  as `positions`
- `velocity_saturation`: Global servo velocity cap, normalized 0.0 to 1.0.
  0.0 uses the firmware default. Per-hand — the wire carries one value for all
  fingers

#### `send_hand_streams(positions, torque=0.45, velocity_saturation=0.0) -> None`

Control all 20 finger joints via streaming channel (high-frequency, requires streaming mode).

**Parameters:**

- `positions`: List of 20 joint angles in radians (5 fingers × 4 joints)
- `torque`: Normalized 0.0 to 1.0. A scalar applies to the whole hand, 5 values
  apply per finger (thumb to pinky), and 20 apply per joint, in the same order
  as `positions`
- `velocity_saturation`: Global servo velocity cap, normalized 0.0 to 1.0.
  0.0 uses the firmware default. Per-hand — the wire carries one value for all
  fingers

**Requires:** Client created with streaming endpoint AND driver in streaming mode.

#### `send_zero_calibration(mask: List[bool]) -> None`

Calibrate zero position for selected joints.

**Parameters:**

- `mask`: List of 16 boolean values indicating which joints to calibrate

#### `poll_event() -> Optional[SystemEvent]` / `drain_events() -> List[SystemEvent]`

Qualified monitoring events. **The status stream is not filtered** — everything
the driver publishes still reaches `try_recv_message()`. Events run beside it and
say a condition has been *established*, which is what you can act on:

| Kind | Meaning |
|---|---|
| `THERMAL_WARNING_CONFIRMED` | A subsystem has been warning long enough to be real, not noise |
| `THERMAL_WARNING_CLEARED` | A confirmed warning stopped recurring |
| `THERMAL_LOCKDOWN` | The hand entered thermal lockdown. Never delayed or debounced |
| `THERMAL_RECOVERED` | The hand came out of lockdown |

```python
for event in client.drain_events():
    if event.kind is SystemEventKind.THERMAL_LOCKDOWN:
        stop_motion()
    elif event.kind is SystemEventKind.THERMAL_WARNING_CONFIRMED:
        print(f"actuator {event.actuator} sustained warning at {event.detail}C")
```

A single noisy temperature sample never produces an event — a warning must persist
across at least two firmware re-assertions (~12s) first. That is the distinction a
lone alert cannot make.

Delivery is by polling, not a callback: a callback would fire from the SDK's
receiver thread, which means re-entering the interpreter from a foreign thread.
`dropped_events` reports anything lost because the bounded queue filled.

#### `system_status() -> SystemStatus`

Aggregate health of the hand — liveness, hand state, handedness, thermal load
and alert rates — in one passive read. **This is the call to reach for**: a lone
alert carries no severity, while a rate and a latched lockdown state do.

```python
s = client.system_status()
if s.thermal_lockdown:
    print("hand is in thermal lockdown")
elif s.worst_warning_percent > 50:
    print(f"actuator {s.worst_actuator} running hot ({s.peak_temp_c}C)")
```

Never consumes a status message or sends a command, so it is safe to poll from a
UI at frame rate. Assembled client-side; nothing is added to the wire for it.

#### `thermal_load() -> List[ThermalLoad]`

Thermal load per subsystem, as a **percentage** rather than a flag. Quiet
subsystems are omitted.

Firmware caps thermal alerts at one per subsystem per 5s, so that ceiling is the
denominator: `warning_percent` is how much of it the subsystem actually used
over the last 60s. A lone temperature excursion reads single digits; a genuinely
hot actuator saturates the channel and reads 100.

Prefer this over reacting to individual warnings — one warning carries no
severity, a percentage does.

```python
for load in client.thermal_load():
    print(f"actuator {load.actuator}: warning {load.warning_percent}% "
          f"lockdown {load.lockdown_percent}% peak {load.peak_temp_c}C")
```

Counted on the raw status stream, ahead of the client-side warning debounce, so
suppressing a transient warning never hides it from these numbers. Counts start
at connect — nothing carries prior history across the socket.

#### `worst_thermal_load() -> Optional[ThermalLoad]`

The most loaded subsystem, lockdown ranked above warning. `None` when nothing
has alerted inside the window. The one-number readout for a status line.

#### `try_recv_status() -> Optional[HandStatus]`

Non-blocking status poll. Returns status if available, None otherwise.

### Functions

#### `discover_usb_devices(max_devices: int = 10) -> List[UsbDevice]`

Find connected ProHand devices via USB.

#### `get_version() -> str`

Get SDK version string.

### Data Classes

#### `HandStatus`

```python
@dataclass
class HandStatus:
    is_valid: bool
    status_type: int  # 0=unknown, 1=rotary, 2=linear
    rotary_positions: List[float]  # 16 joint positions in radians
    linear_positions: List[float]  # 2 wrist positions in radians
```

#### `SystemStatus`

| Field | Meaning |
|---|---|
| `connected` / `ms_since_heartbeat` | Liveness. `connected` stays true for up to 10s after the driver goes silent; the heartbeat is finer-grained |
| `hand_state` | Hand-state code, or `-1` before one is reported. `8` = thermal protection. See the table in `prohand_sdk.h` |
| `handedness` | `0` unknown, `1` left, `2` right |
| `thermal_lockdown` | Latched state, not a rate — it does not age out while the hand is still locked out |
| `worst_warning_percent` / `worst_lockdown_percent` | Worst subsystem's thermal load, as a % of the maximum publishable |
| `worst_actuator` | Actuator carrying that load; `0xFF` when none |
| `peak_temp_c` | Highest temperature on any thermal alert in the window, °C |
| `active_signals` / `alerts_in_window` | Distinct alert signatures, and total alerts, in the window |
| `worst_severity` | `0` info, `1` warning, `2` error |

#### `ThermalLoad`

| Field | Meaning |
|---|---|
| `source` | `AlertSource` bit value (rotary = `0x02`, linear = `0x04`, IMU = `0x10`) |
| `actuator` | Actuator index, or `0xFF` when not actuator-specific |
| `warning_percent` | Warning alerts over the window as a % of the maximum publishable. Saturates at 100 |
| `lockdown_percent` | Same, for thermal-lockdown alerts |
| `warning_count` / `lockdown_count` | Raw counts inside the window |
| `last_temp_c` | Temperature on the most recent alert, °C |
| `peak_temp_c` | Highest temperature seen since connect, °C |

#### `UsbDevice`

```python
@dataclass
class UsbDevice:
    port_name: str
    display_name: str
```

### Streaming Mode

For high-frequency control (100+ Hz), use streaming mode:

```python
# Create client with all endpoints
client = ProHandClient(
    "tcp://127.0.0.1:5562",  # Command endpoint
    "tcp://127.0.0.1:5561",  # Status endpoint
    "tcp://127.0.0.1:5563",  # Hand streaming endpoint
    "tcp://127.0.0.1:5564"   # Wrist streaming endpoint
)

# Enable streaming mode
client.set_streaming_mode(True)

# Wait for streaming to be ready
if client.wait_for_streaming_ready():
    # Now use streaming methods (velocities are implicit max for wrist)
    client.send_hand_streams(positions, torque)
    client.send_wrist_streams(wrist_positions)
```

## Requirements

- Python 3.7 or later
- ProHand headless IPC host running

## Error Handling

```python
from prohand_sdk import ProHandClient, ProHandError, ConnectionError

try:
    client = ProHandClient(
        "tcp://127.0.0.1:5562",  # Command endpoint
        "tcp://127.0.0.1:5561",  # Status endpoint
        "tcp://127.0.0.1:5563",  # Hand streaming endpoint
        "tcp://127.0.0.1:5564"   # Wrist streaming endpoint
    )
    client.send_ping()
except ConnectionError as e:
    print(f"Connection failed: {e}")
except ProHandError as e:
    print(f"SDK error: {e}")
```

## Context Manager

ProHandClient supports the context manager protocol for automatic cleanup:

```python
with ProHandClient(...) as client:
    client.send_ping()
    # Automatically cleaned up on exit
```

## Notes

- The SDK uses ctypes to interface with the native library
- No external Python dependencies required
- Thread-safe for single client instance
- Status polling is non-blocking
- The native library is located in `../lib/` and is automatically discovered by the Python bindings
- Uses `pyproject.toml` for modern Python packaging (PEP 518/621)

## SDK Package

The Python bindings are included in this SDK package and ready to use.

This regenerates:

- `prohand_sdk/prohand_sdk.py`
- `../lib/libprohand_client_sdk.{dylib,so,dll}` (shared library location)

## License

© Proception AI, Inc. 2024-2025
