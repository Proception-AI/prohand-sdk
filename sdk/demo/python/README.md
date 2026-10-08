# ProHand & ProGlove Python SDK Demo - cdylib FFI

Python demonstration programs using the ProHand and ProGlove Client SDKs via dynamic library (cdylib) FFI bindings.

## Overview

These demos showcase how to use the ProHand and ProGlove Client SDKs from Python using ctypes. Both SDKs are distributed as dynamic libraries (`.dylib` on macOS, `.so` on Linux, `.dll` on Windows) with Python bindings, making them easy to integrate from any Python application.

## Architecture

### ProHand SDK

```
┌─────────────────────────────────────┐
│   Python Demo Applications          │
│  (discover, connect, ping, etc.)    │
└─────────────┬───────────────────────┘
              │ uses
┌─────────────▼───────────────────────┐
│  Python SDK (prohand_sdk.py)        │
│  ctypes wrapper around C API        │
└─────────────┬───────────────────────┘
              │ wraps
┌─────────────▼───────────────────────┐
│  C API (prohand_sdk.h)              │
│  Pure C interface                   │
└─────────────┬───────────────────────┘
              │ exports
┌─────────────▼───────────────────────┐
│  Rust SDK (libprohand_client_sdk)   │
│  Dynamic library (.dylib/.so/.dll)  │
└─────────────────────────────────────┘
```

### ProGlove SDK

```
┌─────────────────────────────────────┐
│   Python Demo Applications          │
│  (connect_glove, test_glove)        │
└─────────────┬───────────────────────┘
              │ uses
┌─────────────▼───────────────────────┐
│  Python SDK (proglove_sdk.py)       │
│  ctypes wrapper around C API        │
└─────────────┬───────────────────────┘
              │ wraps
┌─────────────▼───────────────────────┐
│  C API (proglove_sdk.h)             │
│  Pure C interface                   │
└─────────────┬───────────────────────┘
              │ exports
┌─────────────▼───────────────────────┐
│  Rust SDK (libproglove_client_sdk)  │
│  Dynamic library (.dylib/.so/.dll)  │
└─────────────────────────────────────┘
```

## Prerequisites

### Python Requirements

- Python 3.8 or later
- Most demos use only stdlib (ctypes)
- **Kapandji demo** requires `PyYAML` for YAML configuration parsing:
  ```bash
  pip install pyyaml
  ```

### ProHand SDK Library

The Python demos require the ProHand SDK, which should be included in this SDK package:

- Python bindings: `../prohand_sdk/python/prohand_sdk/prohand_sdk.py`
- Library: `../prohand_sdk/lib/libprohand_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)

### ProGlove SDK Library

The ProGlove demos require the ProGlove SDK, which should be included in this SDK package:

- Python bindings: `../proglove_sdk/python/proglove_sdk/proglove_sdk.py`
- Library: `../proglove_sdk/lib/libproglove_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)

## Running Demos

From this directory (`demo/python`):

### 1. Connection Test

Test IPC connection to the headless host:

```bash
just connect
```

**Example output:**

```
================================================================
ProHand IPC Connection Test
================================================================

Connection parameters:
  Command endpoint:       ipc:///tmp/prohand-commands.ipc
  Status endpoint:         ipc:///tmp/prohand-status.ipc
  Hand streaming endpoint: ipc:///tmp/prohand-hand-streaming.ipc
  Wrist streaming endpoint: ipc:///tmp/prohand-wrist-streaming.ipc

>>> Connecting to IPC host...
✅ Successfully connected to IPC host

>>> Testing communication...
✅ Ping successful!

>>> SDK Information:
  Version: 0.1.0

✅ Connection test completed successfully!
```

### 2. Ping Command

Send ping commands to test latency:

```bash
# Send 10 pings with 1s interval (default)
just ping

# Send 5 pings with 0.5s interval
just ping --count 5 --interval 0.5

# Use TCP endpoints instead of IPC
just ping --command-endpoint tcp://127.0.0.1:5562 --status-endpoint tcp://127.0.0.1:5561 --hand-streaming-endpoint tcp://127.0.0.1:5563 --wrist-streaming-endpoint tcp://127.0.0.1:5564
```

**Example output:**

```
================================================================
ProHand Ping Demo
================================================================

Command endpoint:       ipc:///tmp/prohand-commands.ipc
Status endpoint:         ipc:///tmp/prohand-status.ipc
Hand streaming endpoint: ipc:///tmp/prohand-hand-streaming.ipc
Wrist streaming endpoint: ipc:///tmp/prohand-wrist-streaming.ipc
Ping count:       5
Interval:         0.5s

>>> Connecting...
✅ Connected!

[  0.50s] Ping #1 sent ✓
[  1.00s] Ping #2 sent ✓
[  1.50s] Ping #3 sent ✓
[  2.00s] Ping #4 sent ✓
[  2.50s] Ping #5 sent ✓

✅ Sent 5 ping(s) successfully
```

### 3. Test Hand (Individual Joint Testing)

Test each joint of each finger individually:

```bash
# Test all joints with default settings
just test-hand

# Adjust test parameters
just test-hand --delay 0.3 --cycles 3
```

Tests each of the 16 rotary joints:

- Thumb (joints 0-3)
- Index finger (joints 4-7)
- Middle finger (joints 8-11)
- Ring finger (joints 12-15)

### 4. Cyclic Motion

Run continuous sine wave motion patterns:

```bash
# Default settings (10s duration, 1Hz frequency)
just cyclic-motion

# Adjust motion parameters
just cyclic-motion --duration 20 --frequency 2.0 --amp-scale 0.5

# Include abduction motion
just cyclic-motion --include-abduction

# Include thumb in motion
just cyclic-motion --include-thumb

# Exclude wrist
just cyclic-motion --exclude-wrist
```

**Options:**

- `--amp-scale`: Amplitude scale factor (default: 0.8)
- `--frequency`: Motion frequency in Hz (default: 1.0)
- `--duration`: Duration in seconds (default: 10.0)
- `--pub-hz`: Command publish rate (default: 100.0)
- `--include-abduction`: Use abduction motion instead of flexion
- `--include-thumb`: Include thumb in motion patterns
- `--exclude-wrist`: Skip wrist commands

### 5. UDCAP → ProHand (UDP Glove Streaming)

Single-hand UDP → ProHand streaming (human-hand mapping only):

```bash
# Left hand (IPC defaults)
just udcap-left

# Right hand (IPC defaults)
just udcap-right

# Custom UDP port / torque / rate
just udcap-left --udp-port 5556 --torque 0.4 --publish-rate 50
```

Defaults:

- Command: `ipc:///tmp/prohand-commands.ipc`
- Hand streaming: `ipc:///tmp/prohand-hand-streaming.ipc`
- Wrist streaming: `ipc:///tmp/prohand-wrist-streaming.ipc`
- UDP: host `0.0.0.0`, port `5555`
- Torque: `0.3`, publish rate: `60 Hz`

### 6. Kapandji Opposition Test

Runs the Kapandji opposition sequence - thumb touches each fingertip.

**Note:** Requires `PyYAML` to be installed:

```bash
pip install pyyaml
```

```bash
just kapandji
```

______________________________________________________________________

### 7. Connection Test (Glove)

Test IPC/TCP connection to the ProGlove host:

```bash
# IPC connection by hand side
just connect-glove left
just connect-glove right

# TCP connection
just connect-glove tcp 192.168.1.82:5566
```

**Example output:**

```
================================================================
ProGlove IPC Connection Test
================================================================
Connection parameters:
  Mode:     hand: left
  Status endpoint: ipc:///tmp/proglove-left-status.ipc

>>> Connecting to IPC host...
✅ Successfully connected to IPC host

>>> Testing communication...
✅ Ping successful!

>>> SDK Information:
  Version: 0.1.0

✅ Connection test completed successfully!
```

### 8. Test Glove (Tactile Sensor Monitor)

Monitor tactile sensor data from the ProGlove in real-time:

```bash
# Basic usage
just test-glove left
just test-glove right

# With duration limit
just test-glove left --duration 30

# With custom refresh rate
just test-glove left --refresh-rate 20.0

# TCP connection
just test-glove tcp 192.168.1.82:5566
```

**Options:**

- `--hand <left|right>`: Hand side for IPC connection
- `--tcp <addr:port>`: TCP endpoint (e.g., 192.168.1.82:5566)
- `--duration`: Duration in seconds (0 = infinite, default: 0)
- `--refresh-rate`: Terminal refresh rate in Hz (default: 10.0)

Displays all 100 taxels organized by joint segment:

- Thumb (DIP=6, PIP=4, MCP=10)
- Index/Middle/Ring/Pinky (DIP=4, PIP=2, MCP=2 each)
- Palm (Upper=16, Middle=16, Lower=16)

### 9. Rerun Tactile Logger (raw + processed palm viz + recording)

Log tactile data to [Rerun](https://rerun.io) with a spatial **palm** view —
taxels drawn at their real sensor positions — for the **processed** and **raw**
streams side by side. Auto-starts the driver in a tmux session if none is
running, and can record to a native `.rrd` file for later replay.

Requires the `rerun` extra:

```bash
uv pip install rerun-sdk numpy   # or: uv sync --extra rerun
```

```bash
# Live viewer (auto-starts the driver in a tmux session)
just rerun-glove left
just rerun-glove right

# Record to a .rrd instead of the live viewer (reopen with `rerun session.rrd`)
just rerun-glove left --save session.rrd

# Attach to an already-running driver (don't auto-start one)
just rerun-glove left --no-launch
```

**Options:**

- `left|right` or `--endpoint <ep>`: glove status endpoint. The raw node is
  derived automatically (`-status.ipc` → `-raw.ipc`).
- `--save PATH`: record to a Rerun `.rrd` file instead of the live viewer.
- `--duration <s>`: stop after N seconds (0 = until Ctrl+C).
- `--no-launch`: connect to an already-running driver instead of auto-starting one.
- `--keep-driver`: leave the auto-started driver's tmux session running on exit.
- `--no-spawn`: don't open the viewer window (log to the default sink).

The palm layout comes from the bundled taxel SVGs in `src/proglove_demo/assets/`
(the CAD source-of-truth geometry). Raw tactile requires a locally-hosted glove —
the driver only exposes the `-raw.ipc` node for `ipc://` endpoints.

### Run All Demos

```bash
just demo-all
```

## Code Structure

```
python/
├── justfile                    # Build and run recipes
├── pyproject.toml              # Project configuration
├── README.md                   # This file
└── src/
    ├── prohand_demo/
    │   ├── __init__.py         # Package init
    │   ├── utils.py            # Demo utilities
    │   ├── connect.py          # Connection test
    │   ├── ping.py             # Ping command test
    │   ├── test_hand.py        # Individual joint testing
    │   ├── cyclic_motion.py    # Sine wave motion patterns
    │   ├── debug_streaming.py  # Streaming debug utilities
    │   ├── kapandji.py         # Kapandji test (requires PyYAML)
    │   └── udcap_ctrl.py       # UDP glove → ProHand streaming demo
    └── proglove_demo/
        ├── __init__.py         # Package init
        ├── utils.py            # Demo utilities
        ├── connect.py          # ProGlove connection test
        ├── test_glove.py       # Tactile sensor monitor (terminal)
        ├── filter_control.py   # Live filter / baseline control
        ├── test_ota.py         # Firmware OTA update
        ├── rerun_log.py        # Rerun logger: raw + processed palm viz + recording
        ├── taxel_layout.py     # Taxel (x, y) geometry parsed from the bundled SVGs
        └── assets/             # GT1_Vector_Taxels_{left,right}.svg (palm geometry)
```

## API Reference

### Basic Usage

```python
import sys
from pathlib import Path

# Add SDK to path
sdk_path = Path("../prohand_sdk/python")
sys.path.insert(0, str(sdk_path))

from prohand_sdk import ProHandClient, get_version

# Check SDK version
print(f"SDK Version: {get_version()}")

# Connect and send commands
client = ProHandClient(
    "ipc:///tmp/prohand-commands.ipc",      # Command endpoint
    "ipc:///tmp/prohand-status.ipc",        # Status endpoint
    "ipc:///tmp/prohand-hand-streaming.ipc", # Hand streaming endpoint
    "ipc:///tmp/prohand-wrist-streaming.ipc" # Wrist streaming endpoint
)

# Check connection
if client.is_connected():
    print("Connected!")

# Send ping
client.send_ping()

# Control joints (16 rotary joints)
positions = [0.0] * 16  # Radians
torques = [0.45] * 16   # 0.0-1.0
client.send_rotary_commands(positions, torques)

# Control wrist (2 linear motors)
wrist_pos = [0.0, 0.0]  # Radians
wrist_speed = [1.0, 1.0]  # 0.0-1.0
client.send_linear_commands(wrist_pos, wrist_speed)

# Receive status (non-blocking)
status = client.try_recv_status()
if status and status.is_valid:
    print(f"Rotary positions: {status.rotary_positions}")
    print(f"Status type: {status.status_type}")

# Clean up
client.close()
```

### Context Manager

ProHandClient supports context managers for automatic cleanup:

```python
with ProHandClient(
    command_endpoint,
    status_endpoint,
    hand_streaming_endpoint,
    wrist_streaming_endpoint
) as client:
    client.send_ping()
    # Automatically cleaned up on exit
```

### Error Handling

```python
from prohand_sdk import ProHandClient, ConnectionError, ProHandError

try:
    client = ProHandClient(
        command_endpoint,
        status_endpoint,
        hand_streaming_endpoint,
        wrist_streaming_endpoint
    )
    client.send_ping()
except ConnectionError as e:
    print(f"Connection failed: {e}")
except ProHandError as e:
    print(f"SDK error: {e}")
```

______________________________________________________________________

### ProGlove Basic Usage

```python
import sys
from pathlib import Path

# Add SDK to path
sdk_path = Path("../proglove_sdk/python")
sys.path.insert(0, str(sdk_path))

from proglove_sdk import ProGloveClient, get_version

# Check SDK version
print(f"SDK Version: {get_version()}")

# Connect (IPC or TCP)
client = ProGloveClient("ipc:///tmp/proglove-left-status.ipc")
# or: client = ProGloveClient("tcp://192.168.1.82:5566")

# Check connection
if client.is_connected():
    print("Connected!")

# Verify connection
client.send_ping()

# Receive processed (host-filtered) tactile status (non-blocking)
status = client.try_recv_status()
if status and status.is_valid:
    # Finger segments (DIP/PIP/MCP)
    print(f"Thumb DIP: {status.t_dip}")
    print(f"Index MCP: {status.i_mcp}")

    # Palm regions
    print(f"Upper Palm: {status.upper_palm}")

# Pre-filter RAW tactile from the secondary `-raw.ipc` node — pure hardware
# ADC, no baseline/filter. Available on locally-hosted (ipc://) gloves; poll it
# alongside try_recv_status() to capture raw + processed together.
if client.has_raw_tactile():
    raw = client.try_recv_raw_tactile()
    if raw and raw.is_valid:
        print(f"Raw thumb DIP: {raw.t_dip}")

# Clean up
client.close()
```

### TactileStatus Structure

| Field | Size | Description |
|-------|------|-------------|
| `t_dip`, `t_pip`, `t_mcp` | 6, 4, 10 | Thumb segments |
| `i_dip`, `i_pip`, `i_mcp` | 4, 2, 2 | Index finger |
| `m_dip`, `m_pip`, `m_mcp` | 4, 2, 2 | Middle finger |
| `r_dip`, `r_pip`, `r_mcp` | 4, 2, 2 | Ring finger |
| `p_dip`, `p_pip`, `p_mcp` | 4, 2, 2 | Pinky finger |
| `upper_palm` | 16 | Upper palm region |
| `middle_palm` | 16 | Middle palm region |
| `lower_palm` | 16 | Lower palm region |
| `timestamp` | - | Data timestamp |
| `uid` | - | Unique identifier |
| `is_valid` | - | Data validity flag |

## Endpoints

Demos support both IPC and TCP endpoints:

### ProHand Endpoints

**IPC (default, fastest):**

- Command: `ipc:///tmp/prohand-commands.ipc`
- Status: `ipc:///tmp/prohand-status.ipc`
- Hand streaming: `ipc:///tmp/prohand-hand-streaming.ipc`
- Wrist streaming: `ipc:///tmp/prohand-wrist-streaming.ipc`

**TCP (network-accessible):**

- Command: `tcp://127.0.0.1:5562`
- Status: `tcp://127.0.0.1:5561`
- Hand streaming: `tcp://127.0.0.1:5563`
- Wrist streaming: `tcp://127.0.0.1:5564`

### ProGlove Endpoints

**IPC (local, fastest):**

- Left hand: `ipc:///tmp/proglove-left-status.ipc`
- Right hand: `ipc:///tmp/proglove-right-status.ipc`

**TCP (network-accessible):**

- Left hand: `tcp://127.0.0.1:5566`
- Right hand: `tcp://127.0.0.1:5576`

## Running the Host

### ProHand Host

Before running ProHand demos, ensure the ProHand headless IPC host is running.

### ProGlove Host

Before running ProGlove demos, ensure the ProGlove headless IPC host is running.

## Troubleshooting

### SDK Import Error

If you get an import error:

```python
# Check SDK path
python -c "import sys; sys.path.insert(0, '../prohand_sdk/python'); import prohand_sdk; print('OK')"
```

Make sure the SDK files are present in the SDK package.

### Library Not Found

If the dylib can't be loaded:

**macOS:**

```bash
# Check ProHand library exists
ls -la ../prohand_sdk/lib/libprohand_client_sdk.dylib

# Check ProGlove library exists
ls -la ../proglove_sdk/lib/libproglove_client_sdk.dylib

# Set library path if needed
export DYLD_LIBRARY_PATH="$(pwd)/../prohand_sdk/lib:$DYLD_LIBRARY_PATH"
export DYLD_LIBRARY_PATH="$(pwd)/../proglove_sdk/lib:$DYLD_LIBRARY_PATH"
```

**Linux:**

```bash
# Check ProHand library exists
ls -la ../prohand_sdk/lib/libprohand_client_sdk.so

# Check ProGlove library exists
ls -la ../proglove_sdk/lib/libproglove_client_sdk.so

# Set library path if needed
export LD_LIBRARY_PATH="$(pwd)/../prohand_sdk/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH="$(pwd)/../proglove_sdk/lib:$LD_LIBRARY_PATH"
```

### Connection Failures

1. **Check if host is running:**

   ```bash
   ps aux | grep prohand-headless-ipc-host
   ```

1. **Check endpoints match:**

   - Host default: IPC endpoints
   - Demo default: IPC endpoints
   - For TCP, ensure the host is configured for TCP endpoints (see ProHand host documentation)

1. **Check IPC files exist:**

   ```bash
   ls -la /tmp/prohand-*.ipc
   ```

## Installing as Package

You can install the demos as a package:

```bash
# Install in development mode
pip install -e .

# Then run demos directly
prohand-connect
prohand-ping --count 5
prohand-test-hand
prohand-cyclic-motion --duration 5
```

## Comparison with Cap'n Proto SDK

| Feature | cdylib FFI (this) | Cap'n Proto SDK |
|---------|-------------------|-----------------|
| **Language Support** | Any ctypes-capable language | Rust, Python, C++ |
| **Setup** | Dynamic library only | Requires Cap'n Proto |
| **API Complexity** | Simplified | Full-featured |
| **Performance** | Good (minimal FFI overhead) | Best (zero-copy) |
| **Use Case** | Integration, prototyping | High-performance control |
| **Dependencies** | None (stdlib only) | Cap'n Proto + ZMQ |

## See Also

- [ProHand SDK](../prohand_sdk/README.md) - ProHand SDK documentation
- [ProGlove SDK](../proglove_sdk/README.md) - ProGlove SDK documentation
- [C++ Demos](../cpp/) - C++ examples using the same dylib

## License

© Proception AI, Inc. 2024-2025
