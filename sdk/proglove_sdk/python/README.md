# ProGlove SDK - Python Client

Python bindings for the ProGlove tactile sensor glove system.

## Installation

### Option 1: pip install (recommended)

```bash
cd proglove_sdk/python
pip install -e .
```

### Option 2: Direct import

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/proglove_sdk/python"
```

## Quick Start

```python
from proglove_sdk import ProGloveClient, discover_usb_devices, get_version

# Check version
print(f"SDK Version: {get_version()}")

# Discover connected devices
devices = discover_usb_devices()
for device in devices:
    print(f"Found: {device.display_name}")

# Connect to device
with ProGloveClient("tcp://192.168.1.82:5566") as client:
    # Verify connection
    client.send_ping()

    # Poll tactile status
    status = client.try_recv_status()
    if status and status.is_valid:
        print(f"Thumb DIP: {status.t_dip}")
        print(f"Upper Palm: {status.upper_palm}")
```

## API Reference

### ProGloveClient

Main client for receiving tactile sensor data from the ProGlove device.

#### `__init__(status_endpoint: str)`

Create a new client connection.

**Parameters:**

- `status_endpoint`: ZeroMQ endpoint for status (e.g., "tcp://192.168.1.82:5566" or "ipc:///tmp/proglove-left-status.ipc")

#### `send_ping() -> None`

Verify connection by waiting for tactile data.

Since ProGlove uses PUB/SUB (not REQ/REP), this method waits for tactile data to be received, confirming the connection is working.

**Raises:** `ConnectionError` if no data received within timeout (1 second).

#### `is_connected() -> bool`

Check if connected to the device.

#### `try_recv_status() -> Optional[TactileStatus]`

Non-blocking status poll. Returns status if available, None otherwise.

#### `close() -> None`

Close the client and free resources.

### Functions

#### `discover_usb_devices(max_devices: int = 16) -> List[UsbDevice]`

Find connected ProGlove devices via USB.

#### `get_version() -> str`

Get SDK version string.

### Data Classes

#### `TactileStatus`

```python
@dataclass
class TactileStatus:
    is_valid: bool
    timestamp: int
    uid: int
    # Thumb segments (6+10+4 = 20 taxels)
    t_dip: List[int]   # 6 taxels
    t_mcp: List[int]   # 10 taxels
    t_pip: List[int]   # 4 taxels
    # Index segments (4+2+2 = 8 taxels)
    i_dip: List[int]   # 4 taxels
    i_mcp: List[int]   # 2 taxels
    i_pip: List[int]   # 2 taxels
    # Middle segments (4+2+2 = 8 taxels)
    m_dip: List[int]   # 4 taxels
    m_mcp: List[int]   # 2 taxels
    m_pip: List[int]   # 2 taxels
    # Ring segments (4+2+2 = 8 taxels)
    r_dip: List[int]   # 4 taxels
    r_mcp: List[int]   # 2 taxels
    r_pip: List[int]   # 2 taxels
    # Pinky segments (4+2+2 = 8 taxels)
    p_dip: List[int]   # 4 taxels
    p_mcp: List[int]   # 2 taxels
    p_pip: List[int]   # 2 taxels
    # Palm segments (16+16+16 = 48 taxels)
    upper_palm: List[int]   # 16 taxels
    middle_palm: List[int]  # 16 taxels
    lower_palm: List[int]   # 16 taxels
```

Total: 100 taxels per hand. Values are 0-4095 (12-bit ADC), where higher values indicate more pressure.
The default stream is baseline-subtracted with a deadzone, so an unloaded taxel reads 0.

#### `UsbDevice`

```python
@dataclass
class UsbDevice:
    port_name: str
    display_name: str
```

### Polling Mode

For continuous tactile data monitoring:

```python
import time

# Create client
client = ProGloveClient("tcp://192.168.1.82:5566")

# Verify connection
client.send_ping()

# Poll loop
while True:
    status = client.try_recv_status()
    if status and status.is_valid:
        # Process tactile data
        print(f"Thumb DIP: {status.t_dip}")
        print(f"Index MCP: {status.i_mcp}")
        print(f"Upper Palm: {status.upper_palm}")
    time.sleep(0.001)  # Small sleep to avoid busy-waiting
```

## Requirements

- Python 3.7 or later
- ProGlove headless IPC host running

## Error Handling

```python
from proglove_sdk import ProGloveClient, ProGloveError, ConnectionError

try:
    client = ProGloveClient("tcp://192.168.1.82:5566")
    client.send_ping()
except ConnectionError as e:
    print(f"Connection failed: {e}")
except ProGloveError as e:
    print(f"SDK error: {e}")
```

## Context Manager

ProGloveClient supports the context manager protocol for automatic cleanup:

```python
with ProGloveClient("tcp://192.168.1.82:5566") as client:
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

- `proglove_sdk/proglove_sdk.py`
- `../lib/libproglove_client_sdk.{dylib,so,dll}` (shared library location)

## License

© Proception AI, Inc. 2024-2025
