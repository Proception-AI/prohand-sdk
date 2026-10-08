# ProHand SDK Release Index

**Current Release**: 0.3.17.0
**Release Date**: 2026-09-22

## Version Information

- **SDK Version**: 0.3.17.0
- **Firmware Version**: 0.9.11.0
- **macOS App Version**: 0.3.17.0

## Release Contents

### SDK (Unpacked in `sdk/`)

The SDK is provided as unpacked source code and libraries, not as a tarball. This allows for:

- Easy browsing on GitHub
- Direct cloning and use
- Better git diff viewing

**Includes**:

- `sdk/prohand_sdk/` - ProHand SDK (C++, Python)
- `sdk/proglove_sdk/` - ProGlove SDK (C++, Python)
- `sdk/prowrist_sdk/` - ProWristCam SDK (C++, Python)
- `sdk/demo/` - Example applications
- `sdk/docs/` - Documentation

### Driver Binaries (`driver/`)

#### (Defaults) Platform-specific driver bundles (unpacked folders):

- `driver/macos-arm64/` - macOS Apple Silicon
- `driver/linux-arm64/` - Linux ARM64 (Jetson, etc.)
- `driver/linux-x64/` - Linux x64 (Intel/AMD)

#### (Not In this Package) Platform-specific driver binaries packaged as tarballs:

- `prohand-driver-0.3.17.0-macos-arm64.tar.gz` - macOS Apple Silicon
- `prohand-driver-0.3.17.0-linux-arm64.tar.gz` - Linux ARM64 (Jetson, etc.)
- `prohand-driver-0.3.17.0-linux-x64.tar.gz` - Linux x64 (Intel/AMD)

**Included in each driver package**:

- `prohand-headless-ipc-host` - ProHand IPC host driver
- `proglove-headless-ipc-host` - ProGlove IPC host driver
- `prowristcam-headless-ipc-host` - ProWristCam IPC host driver
- `udcap-ctrl` - USB device capture / control utility

### Firmware (`firmware/`)

- `ProHand-fw-esp-L-*-ota.bin` - Left hand OTA firmware
- `ProHand-fw-esp-R-*-ota.bin` - Right hand OTA firmware

### macOS Application (`app/`)

- `ProHand Diagnostic 0.3.17.0.dmg` - Diagnostic and configuration tool

## Installation

### Using the SDK

Since the SDK is unpacked, you can use it directly:

```bash

# Clone the repository

git clone https://github.com/Proception-AI/pro-sdk.git
cd pro-sdk

# Use Python SDK

cd sdk/prohand_sdk/python
python3 example.py

# Use C++ SDK

cd sdk/prohand_sdk/cpp

# See README for build instructions

```

### Using Driver Binaries

The driver binaries ship unpacked under `driver/<platform>/`. Run the host for your platform directly:

```bash

# Example for macOS ARM64

./driver/macos-arm64/prohand-headless-ipc-host --help
```

## Version History

Version management is handled via git tags. To see all releases:

```bash
git tag -l
```

To checkout a specific version:

```bash
git checkout 0.3.17.0
```

## Manifest

See [MANIFEST.txt](MANIFEST.txt) for checksums and detailed file information.

## Support

For documentation and support:

- SDK Documentation: See `sdk/docs/`
- Issues: https://github.com/Proception-AI/pro-sdk/issues
- Email: contact@proception.ai
