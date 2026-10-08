# Changelog

All notable changes to the Proception SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features go here

### Changed
- Changes to existing functionality go here

### Deprecated
- Soon-to-be removed features go here

### Removed
- Removed features go here

### Fixed
- Bug fixes go here

### Security
- Security improvements go here

---

<!-- Version entries will be added below by the packaging script -->

# Release 0.4.13.0

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
