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

## [0.3.17.0] - 2026-09-22

### Added
- SDK version 0.3.17.0
- Firmware version 0.9.11.0
- macOS App version 0.3.17.0

---

## [0.3.4.0] - 2026-08-06

SDK 0.3.4.0 · firmware 0.9.1.0 · macOS app 0.3.4.0

### Added
- Typed status frames for the hand. `prohand_try_recv_message()` (C),
  `try_recv_message()` (Python), `tryRecvMessage()` (C++) return one decoded
  frame per message kind instead of a single flattened struct: rotary and linear
  status, rotary and linear targets, joint, IMU, power, alert, state and
  handedness. Python exposes each as a dataclass (`RotaryStatusFrame`,
  `ImuFrame`, `AlertFrame`, …) with `MessageKind`, `AlertSource`,
  `AlertSeverity`, `ThermalEvent` and `Handedness` enums.
- ABI verification. `prohand_abi_sizes()` reports the library's own struct
  sizes; the Python bindings check all fifteen at import and raise with a
  per-struct mismatch list, rather than silently misreading every field when a
  wrapper is paired with a mismatched library.
- ProGlove filter configuration: `proglove_get_default_filter_config()` and
  `proglove_set_filter_config()`, with a `ProGloveFilterConfig` carrying
  `deadzone_on`, `deadzone_off`, `denoise_enabled`, `stuck_spatial_threshold`
  and `stuck_streak_on_frames`. Fetch the defaults, tweak what you need, then
  apply — the command replaces the whole config, not a per-field patch.
- Demo: `prohand-rerun` (`just demo python rerun-hand`) logs rotary and linear
  feedback alongside the firmware's target echo to Rerun while streaming a
  curl, starting the driver in a tmux session if none is running
  (`--no-launch` to attach to an existing one). Needs the `rerun` extra.
- `sdk/mise.toml` pins the toolchain the SDK and demos are built against —
  Python 3.12.13, uv 0.11.26, just 1.57.0, CMake 4.1.2, Ninja 1.13.2 — so
  `mise install` in `sdk/` is enough to build and run everything below it.

### Changed
- **Breaking (all languages):** `proglove_set_filter_enabled()` /
  `set_filter_enabled()` / `setFilterEnabled()` are removed. There is no
  whole-pipeline disable: subscribe to the driver's secondary raw PUB node
  (`-raw.ipc`) for fully unfiltered ADC values, which — unlike a shared kill
  switch — does not disrupt every other subscriber on the main filtered
  endpoint.
- **Breaking (behavior):** the host-side tactile filter is now baseline
  subtraction → deadzone hysteresis → optional stuck-pixel masking. The
  sliding-median pre-filter and the EMA smoothing stage are both gone, so
  filtered taxel values will differ for the same physical touch.
- `set_denoise_enabled()` keeps its name but gates less: stuck-pixel masking
  alone (flatness streak + spatial isolation from a taxel's physical
  neighbors), where it previously gated the median pre-filter along with it.
- `try_recv_status()` still works and keeps its signature, but reports rotary
  and linear values only, in raw wire units. Prefer `try_recv_message()` for
  new code.
- Rebuilt the driver binaries for macOS arm64, Linux x64 and Linux arm64.

---

## [0.3.3.0] - 2026-07-28

SDK 0.3.3.0 · firmware 0.9.1.0 · macOS app 0.3.3.0

### Added
- Auto-calibration: `prohand_send_auto_calibration()` (C), `send_auto_calibration()`
  (Python), `sendAutoCalibration()` (C++), with `PROHAND_CALIB_*` macros and a
  Python `CalibrationMask` enum for per-finger masks. `0` aborts a running pass.
- Homing: `prohand_send_homing()` / `send_homing()` / `sendHoming()`.
- Driver liveness: `prohand_ms_since_last_heartbeat()` /
  `ms_since_last_heartbeat()` / `msSinceLastHeartbeat()`. Reports the age of the
  last status message, which is finer-grained than `is_connected()` — that stays
  true for up to 10 seconds after the driver goes quiet.
- `velocity_saturation` is now settable on hand commands in all three languages.
- Status reads now expose the commanded targets alongside measured positions
  (`rotary_targets`, `linear_targets`).
- Demos: `prohand_demo.keyframe_motion` plays predefined joint-space sequences
  with per-keyframe easing, warns when a sequence exceeds what the servos can
  track, and offers `--fit-speed` and `--dry-run`. `prohand_demo.command_matrix`
  exercises every SDK entry point and prints a pass/fail/skip table.

### Changed
- **Breaking (C/C++):** `prohand_send_hand_command()` and
  `prohand_send_hand_streams()` take a fourth argument, `uint8_t
  velocity_saturation`. Pass `0` for the default. The C++ wrapper and Python
  bindings default it, so only direct C callers must update.
- **Breaking (C/C++):** `ProHandStatusInfo` now matches the library layout —
  positions are `int16_t` in centidegrees (the header previously declared them
  `float`) and the struct carries `rotary_targets[16]` and `linear_targets[2]`.
  Recompile any C/C++ code that reads status. The C++ wrapper converts to radians
  and exposes the new target vectors.
- `prohand_sdk.h` includes `<stdbool.h>` and keeps its includes outside the
  `extern "C"` block; it now compiles as strict C99 (`-std=c99 -pedantic`).
- Documentation rewritten against the shipped API. `EXAMPLES.md` and the
  quick-start snippets previously showed constructors, argument names and helper
  types that did not exist, and referenced a Rust client that is not part of this
  package. `API.md` corrects `handService`'s `streamingMode` (a
  `StreamingModeTypes` union, not a `Bool`) and `autoCalibration` (a `UInt8`
  finger mask, not a `Bool`), documents the four previously undocumented
  `HandRequest` variants, and documents `velocitySaturation`.
- Rebuilt the driver binaries for macOS arm64, Linux x64 and Linux arm64.

### Fixed
- Python `discover_usb_devices()` aborted the process whenever it found a device.
  The `ProHandUsbDeviceInfo` pointer fields were declared `c_char_p`, and ctypes
  converts such a struct field to `bytes` on read, discarding the original
  pointer — so `prohand_free_string()` was handed a pointer into Python's heap.
- `velocity_saturation = 0`, documented as "use the default velocity", reached the
  servos as a velocity of zero, so joint commands were accepted but the fingers
  did not move. The driver now resolves it to the configured default (50 deg/s).
- `prohand_send_hand_command()` and `prohand_send_hand_streams()` were declared
  with three parameters in the C header and Python bindings while the library
  took four, so an uninitialised byte was passed as the velocity cap.
- `ProHandStatusInfo`'s C declaration disagreed with the library's layout, making
  every C and C++ status read return meaningless values.

---

## [0.3.1.0] - 2026-07-27

### Added
- SDK version 0.3.1.0
- Firmware version 0.9.1.0
- macOS App version 0.3.1.0

---

## [0.3.0.0] - 2026-07-22

### Added
- ProGlove raw tactile API — `try_recv_raw_tactile()` and `has_raw_tactile()`
  (C++ and Python) expose pre-filter hardware ADC frames from the driver's
  secondary raw node, pollable alongside processed frames
- ProGlove Rerun demo (`proglove-rerun` / `just rerun [left|right]`) — logs
  raw + processed tactile to [Rerun](https://rerun.io); install with the
  `rerun` extra
- SDK version 0.3.0.0
- Firmware version 0.9.1.0
- macOS App version 0.3.0.0

---

## [0.2.6.0] - 2026-07-15

### Added
- ProWristCam SDK (C++, Python) — subscribes to a ZeroMQ stream endpoint and
  delivers JPEG frames from the wrist-mounted camera (`WristCamClient`)
- `prowristcam-headless-ipc-host` driver (macOS ARM64)
- `udcap-ctrl` utility — UDP capture control for dual-arm systems (macOS ARM64)
- ProWristCam demos: `connect_wristcam` / `test_wristcam` (C++) and the
  `prowrist_demo` package with a live frame viewer (Python)
- ProGlove OTA update and filter-control demos
- SDK version 0.2.6.0
- Firmware version 0.8.56.0
- macOS App version 0.2.6.0

### Hardware Support
- ProWristCam wrist camera (JPEG streaming)

---

## [v1.0.0-rc] - 2025-12-09

### Added
- Initial SDK release
- ProHand SDK with C++ and Python bindings
- ProGlove SDK with C++ and Python bindings
- 15+ demo applications showcasing SDK capabilities
- Comprehensive API documentation
- Firmware OTA update support
- macOS Diagnostic application

### Platform Support
- macOS ARM64 (Apple Silicon M1/M2/M3/M4)
- Linux ARM64 (Jetson Orin, ARM servers)
- Linux x64 (Intel/AMD processors)

### Hardware Support
- ProHand robotic hand (left and right configurations)
- ProGlove robotic glove
- ESP32-based firmware with wireless connectivity

### Notes
- First public release candidate
- Full IPC communication via ZeroMQ
- Real-time telemetry and control
