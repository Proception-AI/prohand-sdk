# Changelog

All notable changes to the Proception SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features go here

### Changed
- Changes to existing functionality go here

### Fixed
- Bug fixes go here

---

# Release 2.0.2.0

---

## [2.0.2.0] — 2026-10-28

_Components:_ sdk: 2.0.2.0,driver: 2.1.2.0,firmware: 2.0.7.0,

### Added

- A diagram of the wrist range of motion that both wrist actuators can reach

### Changed

- Versions follow the hardware generation: the Gen 2 SDK, driver and firmware start at 2.0. The API does not change from 0.4.26.0
- The two wrist actuators arrive at the target together, so a combined yaw and pitch move goes in a straight path
- Wrist yaw and pitch each report their own signed torque (-1 to 1). Before, both showed the larger actuator effort
- While a host streams, the hand keeps saved settings in memory and writes them after the session, or every 30 minutes. Status frames stay on time during a save
- In torque mode, finger speed is not limited

### Fixed

- A wrist target outside the reachable range goes to the nearest reachable pose. Before, pitch drifted
- Wrist commands and reported angles away from the yaw and pitch axes are correct, and the wrist angle resolves at the corners of the range
- Wrist effort no longer saturates at low current
- Kapandji demo: the slide passes keep a gap between the thumb and the fingers
- A client that does not read the stream no longer delays the stream for the other clients
- The driver stays responsive when clients connect and disconnect quickly
- The hand no longer resets during long finger-cycling sessions or at the end of a firmware update
- IMU readings no longer show occasional spikes

### Security

- The driver uses a Tokio release with the fix for RUSTSEC-2026-0386

---

## [0.4.26.0] — 2026-10-13

_Components:_ sdk: 0.4.26.0, driver: 0.4.26.0, firmware: 1.4.21.0

### Fixed

- Driver binaries and client libraries no longer embed the build machine's directory paths
- API docs for `motion_upload` describe the image as a packed motion library image

---

## [0.4.25.0] — 2026-10-13

_Components:_ sdk: 0.4.25.0, driver: 0.4.25.0, firmware: 1.4.21.0

### Added

- Motion library API in the C, C++ and Python SDKs: `motion_upload` loads a packed library image onto the hand; `motion_play`, `motion_stop`, `motion_pause`, `motion_resume`, `motion_release`, `motion_query` and `motion_set_autoplay` control playback
- Protocol reference clients for Python, C++ and Rust under `protocol/reference/prohand/`, with recorded command and status frames as test fixtures, and the Cap'n Proto wire schema under `protocol/schema/prohand/`
- Python SDK: result codes and constants are generated from the C header (`prohand_sdk._ffi_constants`), and each Python SDK ships ABI tests against its native library

### Changed

- Linux udev rules list each supported USB product by vendor and product ID

### Removed

- The `udcap-ctrl` binary is no longer in `driver/<platform>/`. It is a teleoperation demo, not a driver; the Python version stays in `sdk/demo/python`

---

## [0.4.13.0] — 2026-10-07

_Components:_ sdk: 0.4.13.0,driver: 0.4.14.0,firmware: 1.4.0.0,

### Added

- Synced timestamps on the status stream: every status carries the device header (device time, boot, sequence, dropped count, sync epoch) and tHostUs, the sample time in host time; 0 until the first clock sync and after a device reboot
- Per-joint torque in hand commands and a system-status / poll_event monitoring API (see BEHAVIOR-CHANGES.md)

### Changed

- **BREAKING:** The driver speaks the framed V2 USB protocol and requires ProHand firmware 1.3.0 or later; it does not connect to hands on earlier firmware

> **Notes:**
> - First release of the Gen2 Power product line, on branch release/gen2 (tag gen2/0.4.13.0). Hands on earlier firmware are served by branch release/gen1.
