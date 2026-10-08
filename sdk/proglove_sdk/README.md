# ProGlove SDK - Client Bindings

Multi-language client bindings for ProGlove tactile sensor devices.

## Available Languages

- ✅ **Python** - Full support via ctypes
- ✅ **C/C++** - Full support via direct FFI (cdylib)
- ✅ **Android** - Read-only tactile and IMU over USB OTG, see [android/](android/)
- ❌ **WebAssembly** - Not supported (requires OS-level networking)

## Directory Structure

```
proglove_sdk/
├── python/
│   └── proglove_sdk/
│       ├── proglove_sdk.py           # Python bindings (ctypes)
│       └── __init__.py
│
├── cpp/
│   ├── include/proglove_sdk/
│   │   ├── proglove_sdk.h            # C API header
│   │   └── ProGloveClient.hpp        # C++ RAII wrapper
│   └── CMakeLists.txt                # CMake integration
│
└── lib/
    └── libproglove_client_sdk.{dylib,so,dll}  # Shared library
```

## Demo Examples

See the [demo/](../demo/) directory for complete examples:

```bash
cd ../demo

# Python demos
just python connect-glove left    # Connect to left glove
just python connect-glove right   # Connect to right glove
just python test-glove left       # Monitor tactile sensors
just python filter-control left   # Toggle the tactile filter, observe the effect
just python test-ota left --image firmware.bin   # Flash new firmware

# C++ demos
just cpp build                    # Build all demos
just cpp connect-glove left       # Connect to left glove
just cpp test-glove left          # Monitor tactile sensors
```

See [demo/README.md](../demo/README.md) for detailed usage.

## Quick Start

### Python

```python
import sys
sys.path.append('/path/to/proglove_sdk/python')
import proglove_sdk

# Discover devices
devices = proglove_sdk.discover_usb_devices()
for device in devices:
    print(f"Found: {device.display_name}")

# Connect (TCP - default ports: Left=5566, Right=5576; see configs/devices.yaml left_glove_status / right_glove_status)
client = proglove_sdk.ProGloveClient("tcp://127.0.0.1:5566")

# Verify connection
client.send_ping()

# Poll tactile status
status = client.try_recv_status()
if status and status.is_valid:
    print(f"Thumb DIP: {status.t_dip}")
    print(f"Upper Palm: {status.upper_palm}")
    ...
```

### C++

**Using the C++ wrapper (recommended):**

```cpp
#include <proglove_sdk/ProGloveClient.hpp>
#include <iostream>

using namespace proglove_sdk;

int main() {
    try {
        // Create client (IPC or TCP)
        ProGloveClient client("ipc:///tmp/proglove-left-status.ipc");

        // Check connection
        if (client.isConnected()) {
            std::cout << "Connected!\n";
        }

        // Verify connection by waiting for data
        client.sendPing();

        // Poll tactile status
        auto status = client.tryRecvStatus();
        if (status && status->isValid) {
            std::cout << "Thumb DIP[0]: " << (int)status->t_dip[0] << "\n";
            std::cout << "Upper Palm[0]: " << (int)status->upper_palm[0] << "\n";
        }

    } catch (const SdkException& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
```

**Using the C API directly:**

```cpp
#include <proglove_sdk/proglove_sdk.h>
#include <stdio.h>

int main() {
    // Link with: -L/path/to/proglove_sdk/lib -lproglove_client_sdk

    ProGloveClientHandle* client = proglove_client_create(
        "ipc:///tmp/proglove-left-status.ipc"
    );

    if (client) {
        ProGloveTactileStatus status;
        if (proglove_try_recv_status(client, &status) > 0) {
            printf("Thumb DIP[0]: %d\n", status.t_dip[0]);
        }
        proglove_client_destroy(client);
    }

    return 0;
}
```

## SDK Contents

This SDK package includes:

- `lib/` - Pre-built dynamic libraries (`.dylib` on macOS, `.so` on Linux, `.dll` on Windows)
- `cpp/include/` - C and C++ headers
- `python/` - Python bindings ready to use

## API Reference

### Python Functions

#### `discover_usb_devices() -> List[UsbDevice]`

Find connected ProGlove devices via USB.

#### `get_version() -> str`

SDK version string.

#### `ProGloveClient(status_endpoint: str)`

Create a new ProGlove client connection.

**Parameters:**

- `status_endpoint`: Status endpoint (e.g., "tcp://127.0.0.1:5566")

#### `ProGloveClient.is_connected() -> bool`

Whether the background connection is currently up (auto-reconnects on drop).

#### `ProGloveClient.send_ping() -> None`

Verify connection by waiting for data.

#### `ProGloveClient.try_recv_status() -> Optional[TactileStatus]`

Poll tactile status (non-blocking).

#### `ProGloveClient.try_recv_imu_status() -> Optional[ImuStatus]`

Poll fused IMU orientation quaternion (non-blocking).

#### `ProGloveClient.calibrate(timeout: float = 5.0) -> bool`

Full baseline calibration cycle (clear + snapshot), blocking until committed
or the timeout elapses. Requires streaming to be on.

#### `ProGloveClient.set_denoise_enabled(enabled: bool) -> None`

Toggle stuck-pixel masking.

#### `get_default_filter_config() -> ProGloveFilterConfig` / `ProGloveClient.set_filter_config(config: ProGloveFilterConfig) -> None`

Fetch sensible starting values, tweak `deadzone_on`/`deadzone_off`/
`stuck_spatial_threshold`/`stuck_streak_on_frames`, then apply. Replaces the
whole config, not a per-field patch.

There is no whole-pipeline enable/disable — subscribe to the driver's
secondary raw PUB node (`-raw.ipc`) instead for fully unfiltered ADC values,
without disrupting every other subscriber on the main filtered endpoint.

#### `ProGloveClient.perform_ota(image: bytes, key: bytes, sig: bytes, on_progress=None, timeout: float = 15.0) -> bool`

Full OTA firmware update: sends the image, then answers every firmware page
request automatically, calling `on_progress(pages_sent, total_pages)` after
each page. Blocks until success, firmware-reported failure, or a stall
timeout. `key`/`sig` are 32/64-byte ed25519 values (verification is
currently unenforced firmware-side).

### C++ API

**C++ Wrapper (`ProGloveClient.hpp`):**

- RAII-style resource management
- Exception-based error handling
- High-level methods: `sendPing()`, `tryRecvStatus()`, `tryRecvImuStatus()`,
  `calibrate()`, `setDenoiseEnabled()`, `setFilterConfig()`, `performOta()`
  (takes a `std::function` progress callback), etc.
- See `cpp/include/proglove_sdk/ProGloveClient.hpp` for full API

**C API (`proglove_sdk.h`):**

- Pure C interface for C or C++ projects
- OTA progress is reported via a C function-pointer callback
  (`ProGloveOtaProgressCallback`) passed to `proglove_perform_ota()`
- See `cpp/include/proglove_sdk/proglove_sdk.h` for full API

### Not currently exposed (Rust-only)

A few things exist in the underlying Rust SDK but have no FFI/Python/C++
binding today:

- Generic `send_command`/`send_filter_command` passthrough
- Identity/activation (fleet pairing, Ed25519 device keys) — deliberately
  excluded, not an oversight
- Device metadata query (firmware version, git hash, build date, hardware ID)
- `get_last_heartbeat()`
- `ProcessManager` (auto-launching the `proglove-headless-ipc-host` driver)

## Tactile Data Structure

Taxel data is organized by joint segment (DIP/MCP/PIP per finger):

| Segment | Taxel Count | Description |
|---------|-------------|-------------|
| Thumb DIP | 6 | Thumb distal |
| Thumb MCP | 10 | Thumb metacarpal |
| Thumb PIP | 4 | Thumb proximal |
| Index DIP/MCP/PIP | 4/2/2 | Index finger (8 total) |
| Middle DIP/MCP/PIP | 4/2/2 | Middle finger (8 total) |
| Ring DIP/MCP/PIP | 4/2/2 | Ring finger (8 total) |
| Pinky DIP/MCP/PIP | 4/2/2 | Pinky finger (8 total) |
| Upper Palm | 16 | Upper palm region |
| Middle Palm | 16 | Middle palm region |
| Lower Palm | 16 | Lower palm region |
| **Total** | **100** | Taxels per hand |

## Installation

### Python

```bash
cd python
pip install -e .
```

Or copy the `proglove_sdk/` directory to your project.

### C++

```bash
# Copy headers
cp -r cpp/include/proglove_sdk /usr/local/include/

# Copy library
cp lib/libproglove_client_sdk.* /usr/local/lib/

# Or use CMake find_package (coming soon)
```

## Requirements

### Python

- Python 3.8+
- macOS/Linux/Windows

### C++

- C++17 or later
- CMake 3.15+ (for building examples)

## WebAssembly Support

⚠️ **Currently Not Supported**

The underlying SDK uses:

- `tokio` (OS threading)
- `zeromq` (OS sockets)
- `mio` (OS networking)

These are not available in `wasm32-unknown-unknown`.

**Alternative:** Create a REST API or WebSocket wrapper around the ProGlove host for web applications.

## License

© Proception AI, Inc. 2024-2025
