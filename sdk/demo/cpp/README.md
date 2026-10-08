# ProHand & ProGlove C++ SDK Demo - cdylib FFI

C++ demonstration programs using the ProHand and ProGlove Client SDKs via dynamic library (cdylib) FFI bindings.

## Overview

These demos showcase how to use the ProHand and ProGlove Client SDKs from C++ using the C FFI interface. Both SDKs are distributed as dynamic libraries (`.dylib` on macOS, `.so` on Linux, `.dll` on Windows) with pure C APIs, making them easy to integrate from any C++ application.

## Architecture

### ProHand SDK

```
┌─────────────────────────────────────┐
│   C++ Demo Applications             │
│  (connect, ping, test_hand, etc.)   │
└─────────────┬───────────────────────┘
              │ uses
┌─────────────▼───────────────────────┐
│  C++ Wrapper (ProHandClient.hpp)    │
│  SDK: ../../prohand_sdk/cpp/include/│
│  RAII wrapper around C API          │
└─────────────┬───────────────────────┘
              │ wraps
┌─────────────▼───────────────────────┐
│  C API (prohand_sdk.h)              │
│  SDK: ../../prohand_sdk/cpp/include/│
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
│   C++ Demo Applications             │
│  (connect_glove, test_glove)        │
└─────────────┬───────────────────────┘
              │ uses
┌─────────────▼───────────────────────┐
│  C++ Wrapper (ProGloveClient.hpp)   │
│  SDK: ../../proglove_sdk/cpp/include/│
│  RAII wrapper around C API          │
└─────────────┬───────────────────────┘
              │ wraps
┌─────────────▼───────────────────────┐
│  C API (proglove_sdk.h)             │
│  SDK: ../../proglove_sdk/cpp/include/│
│  Pure C interface                   │
└─────────────┬───────────────────────┘
              │ exports
┌─────────────▼───────────────────────┐
│  Rust SDK (libproglove_client_sdk)  │
│  Dynamic library (.dylib/.so/.dll)  │
└─────────────────────────────────────┘
```

## Prerequisites

### System Dependencies

**macOS** (via Homebrew):

```bash
brew install cmake zeromq cppzmq
```

**Ubuntu/Debian**:

```bash
sudo apt-get install -y build-essential cmake libzmq3-dev
```

### ProHand SDK Library

The C++ demos require the ProHand SDK, which should be included in this SDK package:

- C Header: `../../prohand_sdk/cpp/include/prohand_sdk/prohand_sdk.h`
- C++ Wrapper: `../../prohand_sdk/cpp/include/prohand_sdk/ProHandClient.hpp`
- Library: `../../prohand_sdk/lib/libprohand_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)

### ProGlove SDK Library

The ProGlove demos require the ProGlove SDK, which should be included in this SDK package:

- C Header: `../../proglove_sdk/cpp/include/proglove_sdk/proglove_sdk.h`
- C++ Wrapper: `../../proglove_sdk/cpp/include/proglove_sdk/ProGloveClient.hpp`
- Library: `../../proglove_sdk/lib/libproglove_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)

## Building

From this directory (`demo/cpp`):

```bash
# Build all demos
just build

# Clean build artifacts
just clean
```

This uses CMake to:

1. Fetch dependencies (cxxopts for argument parsing)
1. Link against the ProHand SDK dylib
1. Build all demo executables

## Available Demos

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
# Send 10 pings with 1s delay (default)
just ping

# Send 5 pings with 0.5s delay
just ping --count 5 --delay 0.5

# Use TCP endpoints instead of IPC
just ping --command-endpoint tcp://127.0.0.1:5562 --status-endpoint tcp://127.0.0.1:5561 --hand-streaming-endpoint tcp://127.0.0.1:5563 --wrist-streaming-endpoint tcp://127.0.0.1:5564
```

**Example output:**

```
================================================================
ProHand Ping Demo
================================================================
Configuration:
  Command endpoint:       ipc:///tmp/prohand-commands.ipc
  Status endpoint:         ipc:///tmp/prohand-status.ipc
  Hand streaming endpoint: ipc:///tmp/prohand-hand-streaming.ipc
  Wrist streaming endpoint: ipc:///tmp/prohand-wrist-streaming.ipc
  Ping count: 5
  Delay: 0.5s

>>> Connecting to IPC host...
✅ Connected!

>>> Sending ping commands...
Ping 1/5 - ✓ Success (latency: 234µs)
Ping 2/5 - ✓ Success (latency: 189µs)
Ping 3/5 - ✓ Success (latency: 212µs)
Ping 4/5 - ✓ Success (latency: 198µs)
Ping 5/5 - ✓ Success (latency: 205µs)

✅ Ping test completed!
  Success rate: 5/5 (100%)
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

### 5. Kapandji Opposition Test

**Note:** This is currently a placeholder demo.

```bash
just kapandji
```

______________________________________________________________________

### 6. Connection Test (Glove)

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

### 7. Test Glove (Tactile Sensor Monitor)

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

## Code Structure

```
cpp/
├── CMakeLists.txt              # Build configuration
├── justfile                    # Build and run recipes
├── README.md                   # This file
├── include/
│   ├── prohand_demo/
│   │   └── Utils.hpp           # ProHand demo utilities
│   └── proglove_demo/
│       └── Utils.hpp           # ProGlove demo utilities
└── src/
    ├── connect.cpp             # Connection test
    ├── ping.cpp                # Ping command test
    ├── test_hand.cpp           # Individual joint testing
    ├── cyclic_motion.cpp       # Sine wave motion patterns
    ├── kapandji.cpp            # Kapandji test (placeholder)
    ├── connect_glove.cpp       # ProGlove connection test
    └── test_glove.cpp          # ProGlove tactile sensor monitor
```

**Note:** The C++ wrappers are part of their respective SDKs:

- ProHand: `../../prohand_sdk/cpp/include/prohand_sdk/ProHandClient.hpp`
- ProGlove: `../../proglove_sdk/cpp/include/proglove_sdk/ProGloveClient.hpp`

## API Reference

### ProHandClient Class

Main C++ wrapper class providing RAII-style resource management:

```cpp
#include <prohand_sdk/ProHandClient.hpp>

using namespace prohand_sdk;

// Create client with all endpoints
ProHandClient client(
    "tcp://127.0.0.1:5562",   // Command endpoint
    "tcp://127.0.0.1:5561",   // Status endpoint
    "tcp://127.0.0.1:5563",   // Hand streaming endpoint
    "tcp://127.0.0.1:5564"    // Wrist streaming endpoint
);

// Check connection
bool connected = client.isConnected();

// Send commands
client.sendPing();
client.setStreamingMode(true);

// Rotary commands (16 finger joints)
std::vector<float> positions(16, 0.0f);  // Radians
std::vector<float> torques(16, 0.45f);   // 0.0-1.0
client.sendRotaryCommands(positions, torques);

// Linear commands (2 wrist motors) - low-level actuator control
std::vector<float> wristPos = {0.0f, 0.0f};  // Radians
std::vector<float> wristSpeed = {1.0f, 1.0f}; // 0.0-1.0
client.sendLinearCommands(wristPos, wristSpeed);

// Wrist commands (2 wrist joints) - high-level joint control with IK
std::vector<float> wristJoints = {0.0f, 0.0f};  // Radians (joint angles)
bool useProfiler = false;  // Enable motion profiling
client.sendWristCommands(wristJoints, useProfiler);

// Streaming versions (for high-frequency control)
client.setStreamingMode(true);
client.waitForStreamingReady();
client.sendWristStreams(wristJoints, useProfiler);

// Receive status (non-blocking)
auto status = client.tryRecvStatus();
if (status) {
    std::cout << "Rotary pos 0: " << status->rotaryPositions[0] << " rad\n";
}

```

### Error Handling

All methods throw `prohand_sdk::SdkException` on error:

```cpp
try {
    ProHandClient client(
        commandEndpoint,
        statusEndpoint,
        handStreamingEndpoint,
        wristStreamingEndpoint
    );
    client.sendPing();
} catch (const prohand_sdk::SdkException& e) {
    std::cerr << "SDK error: " << e.what() << "\n";
} catch (const std::exception& e) {
    std::cerr << "Unexpected error: " << e.what() << "\n";
}
```

### Available Methods

#### Connection & Control

- `isConnected()` - Check connection status
- `sendPing()` - Send ping command
- `setStreamingMode(bool)` - Enable/disable streaming mode
- `isRunningState()` - Check if driver is in Running state
- `waitForStreamingReady()` - Wait for streaming connection

#### Rotary Commands (16 finger joints)

- `sendRotaryCommands(positions, torques)` - Via REQ/REP (low frequency)
- `sendRotaryStreams(positions, torques)` - Via PUB/SUB (high frequency, requires streaming mode)

#### Linear Commands (2 wrist motors - low-level actuator control)

- `sendLinearCommands(positions, speeds)` - Via REQ/REP (low frequency)
- `sendLinearStreams(positions, speeds)` - Via PUB/SUB (high frequency, requires streaming mode)

#### Wrist Commands (2 wrist joints - high-level joint control with inverse kinematics)

- `sendWristCommands(positions, use_profiler)` - Via REQ/REP (low frequency)
- `sendWristStreams(positions, use_profiler)` - Via PUB/SUB (high frequency, requires streaming mode)

#### Hand Commands (20 finger joints - high-level joint control with inverse kinematics)

- `sendHandCommands(positions, torque, velocitySaturation)` - Via REQ/REP (low frequency)
- `sendHandStreams(positions, torque, velocitySaturation)` - Via PUB/SUB (high frequency, requires streaming mode)
  - `torque` is a scalar (whole hand) or a `std::vector<float>` of 5 (per finger) or 20 (per joint)
  - `velocitySaturation` is normalized 0.0-1.0; 0.0 uses the firmware default

#### Calibration

- `sendZeroCalibration(mask)` - Zero calibration for selected joints

#### Status & Discovery

- `tryRecvStatus()` - Non-blocking status receive
- `discoverUsbDevices()` - Static method to discover USB devices
- `getVersion()` - Static method to get SDK version

______________________________________________________________________

### ProGloveClient Class

Main C++ wrapper for ProGlove tactile sensor devices:

```cpp
#include <proglove_sdk/ProGloveClient.hpp>

using namespace proglove_sdk;

// Create client
ProGloveClient client("tcp://192.168.1.82:5566");

// Check connection
bool connected = client.isConnected();

// Verify connection by waiting for data
client.sendPing();

// Poll tactile status (non-blocking)
auto status = client.tryRecvStatus();
if (status && status->isValid) {
    // Finger segments (DIP/PIP/MCP)
    std::cout << "Thumb DIP[0]: " << (int)status->t_dip[0] << "\n";
    std::cout << "Index MCP[0]: " << (int)status->i_mcp[0] << "\n";

    // Palm regions
    std::cout << "Upper Palm[0]: " << (int)status->upper_palm[0] << "\n";
}
```

#### TactileStatus Structure

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
| `isValid` | - | Data validity flag |

#### Error Handling

All methods throw `proglove_sdk::SdkException` on error:

```cpp
try {
    ProGloveClient client("tcp://192.168.1.82:5566");
    client.sendPing();

    while (true) {
        auto status = client.tryRecvStatus();
        if (status && status->isValid) {
            // Process tactile data
        }
    }
} catch (const proglove_sdk::SdkException& e) {
    std::cerr << "SDK error: " << e.what() << "\n";
} catch (const std::exception& e) {
    std::cerr << "Unexpected error: " << e.what() << "\n";
}
```

#### Available Methods

##### Connection & Control

- `isConnected()` - Check connection status
- `sendPing()` - Verify connection by waiting for tactile data (blocking, 1s timeout)

##### Status Polling

- `tryRecvStatus()` - Non-blocking tactile status receive, returns `std::optional<TactileStatus>`

##### Discovery & Info

- `discoverUsbDevices()` - Static method to discover ProGlove USB devices
- `getVersion()` - Static method to get SDK version string

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

### Library Not Found

If you get a library load error:

**macOS:**

```bash
# Check ProHand library exists
ls -la ../../prohand_sdk/lib/libprohand_client_sdk.dylib

# Check ProGlove library exists
ls -la ../../proglove_sdk/lib/libproglove_client_sdk.dylib

# Add to dylib path
export DYLD_LIBRARY_PATH="$(pwd)/../../prohand_sdk/lib:$DYLD_LIBRARY_PATH"
export DYLD_LIBRARY_PATH="$(pwd)/../../proglove_sdk/lib:$DYLD_LIBRARY_PATH"
```

**Linux:**

```bash
# Check ProHand library exists
ls -la ../../prohand_sdk/lib/libprohand_client_sdk.so

# Check ProGlove library exists
ls -la ../../proglove_sdk/lib/libproglove_client_sdk.so

# Add to library path
export LD_LIBRARY_PATH="$(pwd)/../../prohand_sdk/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH="$(pwd)/../../proglove_sdk/lib:$LD_LIBRARY_PATH"
```

### CMake Can't Find SDK Headers

Make sure the SDK files are present in the SDK package:

- `../../prohand_sdk/cpp/include/prohand_sdk/prohand_sdk.h`
- `../../prohand_sdk/lib/libprohand_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)
- `../../proglove_sdk/cpp/include/proglove_sdk/proglove_sdk.h`
- `../../proglove_sdk/lib/libproglove_client_sdk.dylib` (or `.so` on Linux, `.dll` on Windows)

### Connection Failures

1. **Check if host is running:**

   ```bash
   ps aux | grep prohand-headless-ipc-host
   ```

1. **Check endpoints match:**

   - Host default: IPC endpoints
   - Demo default: IPC endpoints
   - For TCP, ensure host is configured for TCP endpoints

1. **Check IPC files exist:**

   ```bash
   ls -la /tmp/prohand-*.ipc
   ```

## Comparison with Cap'n Proto SDK

| Feature | cdylib FFI (this) | Cap'n Proto SDK |
|---------|-------------------|-----------------|
| **Language Support** | Any C FFI language | Rust, Python, C++ |
| **Setup** | Dynamic library only | Requires Cap'n Proto |
| **API Complexity** | Simplified | Full-featured |
| **Performance** | Good (minimal FFI overhead) | Best (zero-copy) |
| **Use Case** | Integration, prototyping | High-performance control |
| **Dependencies** | None (just dylib) | Cap'n Proto + ZMQ |

## See Also

- [ProHand SDK](../prohand_sdk/README.md) - ProHand SDK documentation
- [ProGlove SDK](../proglove_sdk/README.md) - ProGlove SDK documentation
- [Python Demos](../python/) - Python examples using the same dylib

## License

© Proception AI, Inc. 2024-2025
