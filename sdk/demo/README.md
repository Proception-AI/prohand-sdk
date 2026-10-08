# ProHand & ProGlove Client SDK - Demo Examples

Demo examples using the cdylib-based client bindings (Python & C++).

## Overview

These demos showcase the ProHand and ProGlove Client SDK's direct C FFI (cdylib) bindings. These use a simplified dynamic library interface for easier cross-language integration.

## Current API

The current cdylib FFI exposes:

- **IPC Connection**: Connect to the headless IPC host (4 endpoints: command, status, hand streaming, wrist streaming)
- **Basic Commands**: Send ping, check connection status
- **Hand Control**: Send rotary/linear commands, hand states, zero calibration
- **Streaming Mode**: High-frequency control via PUB/SUB channels (100+ Hz)

The current cdylib FFI exposes (proglove):

- **IPC Connection**: Connect to the headless IPC host (status endpoint)
- **Tactile Data**: Receive 100 taxels organized by finger segments (DIP/MCP/PIP)

## Directory Structure

```
demo/
├── justfile              # Build automation (module loader)
├── README.md             # This file
├── config/               # Configuration files
│   └── kapandji.yaml    # Kapandji test configuration
├── python/               # Python examples
│   ├── justfile
│   ├── pyproject.toml    # Python project configuration
│   ├── README.md         # Python documentation
│   └── src/
│       ├── prohand_demo/
│       │   ├── connect.py        # Connect to IPC host
│       │   ├── ping.py           # Send ping command
│       │   ├── cyclic_motion.py  # Sine wave motion
│       │   ├── keyframe_motion.py # Predefined keyframe sequences
│       │   ├── command_matrix.py # Every SDK command, pass/fail report
│       │   ├── kapandji.py       # Kapandji opposition test
│       │   ├── test_hand.py      # Individual joint testing
│       │   ├── debug_streaming.py # Streaming debug utilities
│       │   └── utils.py          # ProHand demo utilities
│       └── proglove_demo/        # ProGlove demos
│           ├── connect.py        # Connect to glove IPC
│           ├── test_glove.py     # Tactile sensor monitor
│           └── utils.py          # ProGlove demo utilities
└── cpp/                  # C++ examples
    ├── justfile          # C++ build/run commands
    ├── CMakeLists.txt    # CMake build configuration
    ├── README.md         # C++ documentation
    ├── include/
    │   ├── prohand_demo/Utils.hpp   # ProHand demo utilities
    │   └── proglove_demo/Utils.hpp  # ProGlove demo utilities
    └── src/
        ├── connect.cpp        # Connection testing
        ├── ping.cpp           # Ping command
        ├── test_hand.cpp      # Individual joint testing
        ├── cyclic_motion.cpp  # Sine wave motion patterns
        ├── kapandji.cpp       # Kapandji test (placeholder)
        ├── connect_glove.cpp  # ProGlove connection testing
        └── test_glove.cpp     # ProGlove tactile sensor monitor

**Note:** The C++ wrappers are part of their respective SDKs:
- ProHand: `../prohand_sdk/cpp/include/prohand_sdk/ProHandClient.hpp`
- ProGlove: `../proglove_sdk/cpp/include/proglove_sdk/ProGloveClient.hpp`
- Include: `#include <prohand_sdk/ProHandClient.hpp>` or `#include <proglove_sdk/ProGloveClient.hpp>`
- Namespace: `prohand_sdk` or `proglove_sdk`
```

## Quick Start

### Prerequisites

**For ProHand demos:**

1. **ProHand headless IPC host running** (must be started separately)
1. **ProHand device connected** via USB

**For ProGlove demos:**

1. **ProGlove headless IPC host running** (must be started separately)
1. **ProGlove device connected** via USB

### Python Demos

```bash
cd python

# Check Python and SDK
just check

# Test connection
just connect

# Send ping commands
just ping

# Test individual joints
just test-hand

# Run cyclic motion patterns
just cyclic-motion

# Play a predefined keyframe sequence (template, abduction, count, wave, rock-on, fist-wrist)
just keyframe-motion --sequence template
# Preview the trajectory without moving the hand
just keyframe-motion --sequence template --dry-run
# List a sequence's keyframes
just keyframe-list count

# Exercise every SDK command and print a pass/fail/skip table
just command-matrix
# ...including auto-calibration and homing (MOVES THE HAND)
just command-matrix --include-calibration

# Run Kapandji test (requires PyYAML: `pip install pyyaml` or `uv pip install pyyaml`)
just kapandji

# Debug streaming mode connectivity
just debug-streaming

# Run all basic demos
just demo-all

# Show help for all demos
just help-all

# Test ProGlove connection
just connect-glove left
# or: just connect-glove right
# or: just connect-glove --status-endpoint tcp://192.168.1.82:5566

# Monitor tactile sensor data
just test-glove left
# or: just test-glove right
# or: just test-glove --status-endpoint tcp://192.168.1.82:5566
```

### C++ Demos

```bash
cd cpp

# Build all demos
just build

# Clean build artifacts
just clean

# Check SDK availability
just check

# Test connection
just connect

# Send ping commands
just ping

# Test individual joints
just test-hand

# Run cyclic motion patterns
just cyclic-motion

# Run Kapandji test (placeholder)
just kapandji

# Test ProGlove connection
just connect-glove left
# or: just connect-glove right
# or: just connect-glove --status-endpoint tcp://192.168.1.82:5566

# Monitor tactile sensor data
just test-glove left
# or: just test-glove right
# or: just test-glove --status-endpoint tcp://192.168.1.82:5566
```

## C++ Demo Structure

The C++ demos provide a complete example of using the cdylib FFI from C++:

**ProHand SDK Layer** (`../prohand_sdk/cpp/include/prohand_sdk/`):

- `ProHandClient.hpp` - RAII-style C++ wrapper around the C API
- `prohand_sdk.h` - Pure C API header

**ProGlove SDK Layer** (`../proglove_sdk/cpp/include/proglove_sdk/`):

- `ProGloveClient.hpp` - RAII-style C++ wrapper around the C API
- `proglove_sdk.h` - Pure C API header

**Demo Utilities** (`cpp/include/`):

- `prohand_demo/Utils.hpp` - ProHand demo utilities
- `proglove_demo/Utils.hpp` - ProGlove demo utilities

**ProHand Demo Applications** (`cpp/src/`):

- `connect.cpp` - Connection testing
- `ping.cpp` - Latency testing with configurable count/delay
- `test_hand.cpp` - Individual joint testing (all 16 rotary joints)
- `cyclic_motion.cpp` - Sine wave motion patterns with various options
- `kapandji.cpp` - Kapandji opposition test (placeholder)

**ProGlove Demo Applications** (`cpp/src/`):

- `connect_glove.cpp` - ProGlove connection testing
- `test_glove.cpp` - Tactile sensor monitor (100 taxels per hand)

See [cpp/README.md](cpp/README.md) for detailed C++ documentation.

## Comparison with Cap'n Proto SDK

| Feature | Cap'n Proto SDK | cdylib FFI SDK |
|---------|----------------|----------------|
| **Language Support** | Rust, Python, C++ | Python, C++ (+ any C FFI language) |
| **API Complexity** | Full featured | Simplified |
| **Setup** | Requires Cap'n Proto | Just dynamic library (`.dylib/.so/.dll`) |
| **Performance** | Highest (zero-copy) | Good (FFI overhead minimal) |
| **Use Case** | High-performance control | Integration, scripting, prototyping |
| **Bindings** | Cap'n Proto codegen | Manual C FFI + ctypes/JNI/etc |

## See Also

**ProHand:**

- [ProHand SDK](../prohand_sdk/README.md) - Python & C++ bindings
- [ProHand C++ Documentation](cpp/README.md) - Detailed C++ API reference
- [ProHand Python Documentation](python/README.md) - Detailed Python API reference

**ProGlove:**

- [ProGlove SDK Bindings](../proglove_sdk/README.md) - Python & C++ bindings

## License

© Proception AI, Inc. 2024-2025
