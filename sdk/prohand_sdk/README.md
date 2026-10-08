# ProHand SDK - Client Bindings

Multi-language client bindings for ProHand devices.

## Available Languages

- ✅ **Python** - Full support via ctypes
- ✅ **C/C++** - Full support via direct FFI (cdylib)
- ❌ **WebAssembly** - Not supported (requires OS-level networking)

## Directory Structure

```
prohand_sdk/
├── python/
│   └── prohand_sdk/
│       ├── prohand_sdk.py           # Python bindings (ctypes)
│       └── __init__.py
│
├── cpp/
│   ├── include/prohand_sdk/
│   │   ├── prohand_sdk.h            # C API header
│   │   └── ProHandClient.hpp        # C++ RAII wrapper
│   └── CMakeLists.txt               # CMake integration
│
└── lib/
    └── libprohand_client_sdk.{dylib,so,dll}  # Shared library
```

## Demo Examples

See the [demo/](../demo/) directory for complete examples:

```bash
cd ../demo

# Python demos
just python connect      # Connect to IPC
just python ping         # Send pings
just python test-hand    # Test individual joints

# C++ demos
just cpp build          # Build demos
just cpp connect        # Connect to IPC
just cpp ping           # Send pings
```

See [demo/README.md](../demo/README.md) for detailed usage.

## Quick Start

### Python

```python
import sys
sys.path.append('/path/to/prohand_sdk/python')
import prohand_sdk

# Discover devices
devices = prohand_sdk.discover_usb_devices()
for device in devices:
    print(f"Found: {device.display_name}")

# Connect
client = prohand_sdk.ProHandClient(
    "tcp://127.0.0.1:5562",  # Command endpoint
    "tcp://127.0.0.1:5561",  # Status endpoint
    "tcp://127.0.0.1:5563",  # Hand streaming endpoint
    "tcp://127.0.0.1:5564"   # Wrist streaming endpoint
)

# Send ping
client.send_ping()
```

### C++

**Using the C++ wrapper (recommended):**

```cpp
#include <prohand_sdk/ProHandClient.hpp>
#include <iostream>

using namespace prohand_sdk;

int main() {
    try {
        // Create client with all endpoints
        ProHandClient client(
            "tcp://127.0.0.1:5562",   // Command endpoint
            "tcp://127.0.0.1:5561",   // Status endpoint
            "tcp://127.0.0.1:5563",   // Hand streaming endpoint
            "tcp://127.0.0.1:5564"    // Wrist streaming endpoint
        );

        // Check connection
        if (client.isConnected()) {
            std::cout << "Connected!\n";
        }

        // Send commands
        client.sendPing();

        // Wrist commands (high-level joint control)
        std::vector<float> wristPos = {0.0f, 0.0f};
        client.sendWristCommands(wristPos, false);

        // Hand commands (high-level joint control)
        std::vector<float> handPos(20, 0.0f);
        client.sendHandCommands(handPos, 0.45f);

        // Per-finger torque: light thumb, firm index (thumb→pinky)
        client.sendHandCommands(handPos, {0.2f, 0.6f, 0.45f, 0.45f, 0.45f});

    } catch (const SdkException& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
```

**Using the C API directly:**

```cpp
#include <prohand_sdk/prohand_sdk.h>
#include <stdio.h>

int main() {
    // Link with: -L/path/to/prohand_sdk/lib -lprohand_client_sdk

    ProHandClientHandle* client = prohand_client_create(
        "tcp://127.0.0.1:5562",   // Command endpoint
        "tcp://127.0.0.1:5561",   // Status endpoint
        "tcp://127.0.0.1:5563",   // Hand streaming endpoint
        "tcp://127.0.0.1:5564"    // Wrist streaming endpoint
    );

    if (client) {
        prohand_send_ping(client);
        prohand_client_destroy(client);
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

Find connected ProHand devices via USB.

#### `ProHandClient(command_endpoint: str, status_endpoint: str, hand_streaming_endpoint: str, wrist_streaming_endpoint: str)`

Create a new ProHand client connection.

**Parameters:**

- `command_endpoint`: Command endpoint (e.g., "tcp://127.0.0.1:5562")
- `status_endpoint`: Status endpoint (e.g., "tcp://127.0.0.1:5561")
- `hand_streaming_endpoint`: Hand streaming endpoint (e.g., "tcp://127.0.0.1:5563")
- `wrist_streaming_endpoint`: Wrist streaming endpoint (e.g., "tcp://127.0.0.1:5564")

#### `ProHandClient.send_ping() -> None`

Send a ping command to the device.

### C++ API

**C++ Wrapper (`ProHandClient.hpp`):**

- RAII-style resource management
- Exception-based error handling
- High-level methods: `sendWristCommands()`, `sendHandCommands()`, etc.
- See `cpp/include/prohand_sdk/ProHandClient.hpp` for full API

**C API (`prohand_sdk.h`):**

- Pure C interface for C or C++ projects
- See `cpp/include/prohand_sdk/prohand_sdk.h` for full API

## Installation

### Python

```bash
cd python
pip install -e .
```

Or copy the `prohand_sdk/` directory to your project.

### C++

```bash
# Copy headers
cp -r cpp/include/prohand_sdk /usr/local/include/

# Copy library
cp lib/libprohand_client_sdk.* /usr/local/lib/

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

**Alternative:** Create a REST API or WebSocket wrapper around the ProHand host for web applications.

## License

© Proception AI, Inc. 2024-2025
