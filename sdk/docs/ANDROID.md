# Proception Glove — Android integration

This document describes how to read tactile and IMU data from a Proception
Glove on an Android device over USB OTG.

The glove is a USB device. Android gives no process direct access to a serial
node, so your application opens the device through `UsbManager` and moves the
bytes itself. The supplied native library does the protocol work: it turns the
bytes into decoded frames, and it builds the two commands you must send.

## What you get

| File | Purpose |
|---|---|
| `jni/arm64-v8a/libglove_proto.so` | The protocol library, Android arm64 |
| `include/glove_proto.h` | The C API. Generated from the library sources |

Minimum Android API level 21. The library is 16 KB page aligned, which Android
15 and later require on arm64.

## USB

| Property | Value |
|---|---|
| Vendor ID | `0x0483` |
| Product ID | `0x5741` |
| Interface | 0, vendor class |
| Endpoints | One bulk IN, one bulk OUT |

Claim interface 0 and use `UsbDeviceConnection.bulkTransfer()` in both
directions. The device is not CDC-ACM, so a generic USB-serial library cannot
drive it. There is no baud rate to set.

The user must grant USB permission. Call `UsbManager.requestPermission()` and
wait for your broadcast before you open the device. Android shows no second
dialog while one is open, so request permission for one device at a time.

## Sequence

1. `glove_proto_create(hand)` — one session per glove. `hand` is 0 for left, 1 for right.
1. Write `glove_proto_encode_streaming(true, …)` to the bulk OUT endpoint. This starts the data stream.
1. Write `glove_proto_encode_ping(…)` once each second. The device stops streaming if the heartbeat stops.
1. Read the bulk IN endpoint in a loop, and pass each read to `glove_proto_feed()`. It returns the number of complete frames that are ready.
1. Drain with `glove_proto_next_status()` until it returns 0.
1. Classify each payload with `glove_proto_status_kind()`, then decode it with `glove_proto_decode_tactile()` or `glove_proto_decode_imu()`.
1. Write `glove_proto_encode_streaming(false, …)` and call `glove_proto_destroy()` when you close.

Read `glove_proto_handedness()` after the first frames arrive. It reports the
side that the glove firmware declares. If it disagrees with the side you gave
to `glove_proto_create()`, you have the other glove: destroy the session and
create it again with the correct side.

A session is not thread safe. Feed it and drain it from one thread.

## Data

**Tactile** — 100 taxels, each a raw 12-bit value (0 to 4095). The array is
flat, in segment order: thumb DIP, MCP, PIP; then index, middle, ring and
little finger in the same three-part order; then upper, middle and lower palm.
Call `glove_proto_taxel_count()` to confirm the length at runtime.

Values are filtered by default: a subtracted baseline, an exponential moving
average, and a de-noise step. Call `glove_proto_set_filter_enabled(h, false)`
for raw values. Call `glove_proto_snapshot_baseline()` with the hand at rest to
take a new baseline; a `BASELINE_COMMITTED` payload follows when it is stored.

**IMU** — one unit quaternion, in the order w, x, y, z.

**Timestamps** — device milliseconds, 16-bit. They wrap about every 65
seconds, so compare them as differences, not as absolute values.

**Frame sequence** — the `uid` field on a tactile frame increases by one per
frame. A gap means a dropped frame.

## Buffers

Size every output buffer with the constants in the header:
`GLOVE_PROTO_MAX_STATUS_LEN` for a payload, `GLOVE_PROTO_TAXEL_COUNT` for a
tactile frame. `glove_proto_next_status()` returns 0 and discards the payload
when the buffer is too small, so an undersized buffer looks like silence.

## Calling the library from Java or Kotlin

Write a small JNI shim in C that includes `glove_proto.h`, and package it with
`libglove_proto.so` under `jniLibs/arm64-v8a/`. Keep the feed-and-drain loop
inside the shim where you can: it runs at the frame rate, and one JNI call per
USB read costs less than one call per frame.

## Problems

| Symptom | Cause |
|---|---|
| No permission dialog | Another dialog is open, or the request was posted again too soon. Wait, then request once for one device |
| `claimInterface` fails | Another process owns the device. Only one owner at a time |
| Frames stop after a few seconds | The 1 s ping stopped. The device watchdog closed the stream |
| `glove_proto_feed()` always returns 0 | The streaming command was not written, or the write went to the wrong endpoint |
| Every taxel reads near zero | The filter has a baseline from a loaded hand. Take a new baseline at rest |
| The library does not load on Android 15 | The device needs a 16 KB aligned build. Use the supplied library, not a rebuild |
