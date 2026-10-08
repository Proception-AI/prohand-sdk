# ProHand SDK Release Index

**Current Release**: 0.4.13.0
**Release Date**: 2026-10-07

## Version Information

- **SDK Version**: 0.4.13.0
- **Firmware Version**: 1.4.0.0
- **macOS App Version**: 0.4.13.0

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

Platform-specific driver bundles, unpacked:

- `driver/macos-arm64/` - macOS Apple Silicon
- `driver/linux-arm64/` - Linux ARM64 (Jetson, etc.)
- `driver/linux-x64/` - Linux x64 (Intel/AMD)

**Included in each driver bundle**:

- `prohand-headless-ipc-host` - ProHand IPC host driver
- `proglove-headless-ipc-host` - ProGlove IPC host driver
- `prowristcam-headless-ipc-host` - ProWristCam IPC host driver
- `udcap-ctrl` - USB device capture / control utility

Firmware and the desktop application ship through their own channels; the
versions above say which ones this release was built against.

## Installation

### Using the SDK

Since the SDK is unpacked, you can use it directly:

```bash

# Clone the repository

git clone --branch release/gen2 --single-branch https://github.com/Proception-AI/prohand-sdk.git
cd prohand-sdk

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

This release is on the `gen2` product line (branch
`release/gen2`). Every release of a line is a tag named
`<line>/<sdk-version>`:

```bash
git tag -l 'gen2/*'
```

To check out this release:

```bash
git checkout gen2/0.4.13.0
```

Other product lines have their own branches; see the README on `main`.

## Manifest

See [MANIFEST.txt](MANIFEST.txt) for checksums and detailed file information.

## Support

For documentation and support:

- SDK Documentation: See `sdk/docs/`
- Issues: https://github.com/Proception-AI/prohand-sdk/issues
- Email: contact@proception.ai
