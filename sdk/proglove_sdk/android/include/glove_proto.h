/*
 * Proception Glove — wire protocol C API
 *
 * GENERATED FILE — do not edit.
 * Regenerate with: just crates glove-proto-ffi header
 *
 * One session per glove. Feed it the bytes read from the device, drain the
 * queued status payloads, and decode the ones you want:
 *
 *   glove_proto_create(hand)                       0 = left, 1 = right
 *   write glove_proto_encode_streaming(true, …)    start the stream
 *   write glove_proto_encode_ping(…) every 1 s     feed the device watchdog
 *   glove_proto_feed(h, bytes, len)                -> queued payload count
 *   glove_proto_next_status(h, out, cap)           -> length, 0 = none left
 *   glove_proto_status_kind(payload, len)          -> GLOVE_PROTO_KIND_*
 *   glove_proto_decode_tactile / _decode_imu       -> values
 *   glove_proto_destroy(h)
 *
 * A payload from glove_proto_next_status is byte-identical to what the desktop
 * host driver publishes, so an existing consumer can take it unchanged.
 *
 * Units are wire units. Taxels are raw 12-bit ADC counts (0-4095) in segment
 * order t_dip..lower_palm. The IMU quaternion is [w, x, y, z], unit norm.
 * Timestamps are device milliseconds, 16-bit and wrapping.
 *
 * A session is NOT thread-safe: feed and drain it from one thread.
 */

#ifndef GLOVE_PROTO_H
#define GLOVE_PROTO_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#define GLOVE_PROTO_TAXEL_COUNT 100

/* Tags 7 and 8 belong to functions outside this SDK. Ignore those payloads. */

/**
 * Safe caller-side buffer size for any single status payload.
 * Worst case is `TactileStatus`: ~100 × u16 varints (≤3 B each) + header.
 */
#define GLOVE_PROTO_MAX_STATUS_LEN 512

/**
 * Status payload kinds, matching postcard's declaration-order enum tags
 * (NOT the `#[repr(u8)]` discriminants — postcard ignores those).
 */
#define GLOVE_PROTO_KIND_PONG 0

#define GLOVE_PROTO_KIND_TIME_SYNC 1

#define GLOVE_PROTO_KIND_GLOVE_SERVICE 2

#define GLOVE_PROTO_KIND_TACTILE 3

#define GLOVE_PROTO_KIND_IMU 4

#define GLOVE_PROTO_KIND_HANDEDNESS 5

#define GLOVE_PROTO_KIND_BASELINE_COMMITTED 6

#define GLOVE_PROTO_KIND_METADATA 9

#define GLOVE_PROTO_KIND_RAW_TACTILE_FRAME 10

#define GLOVE_PROTO_KIND_RAW_POSITION_FRAME 11

/**
 * Per-hand protocol session: COBS reassembly buffer + outgoing payload queue.
 */
typedef struct GloveProto GloveProto;

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

/**
 * Create a session. `hand`: 0 = left, 1 = right (selects the filter state
 * and is compared against the firmware's Handedness report).
 */
struct GloveProto *glove_proto_create(uint8_t hand);

/**
 * # Safety
 * `h` must be null or a live handle from [`glove_proto_create`]; it is
 * invalid after this call.
 */
void glove_proto_destroy(struct GloveProto *h);

/**
 * Feed raw serial bytes; returns the number of queued status payloads.
 *
 * Split on 0x00, COBS+postcard decode, apply the tactile filter in place
 * (unless disabled via [`glove_proto_set_filter_enabled`]), track handedness,
 * and queue each message re-encoded as a plain-postcard payload (a committed
 * baseline queues a follow-up `BaselineCommitted`).
 *
 * # Safety
 * `data` must point to `len` valid bytes (may be null iff `len == 0`).
 */
size_t glove_proto_feed(struct GloveProto *h, const uint8_t *data, size_t len);

/**
 * Pop the next status payload into `out` (≥ [`GLOVE_PROTO_MAX_STATUS_LEN`]
 * recommended). Returns the payload length, or 0 when the queue is empty or
 * `cap` is too small (the payload is dropped in that case — size buffers
 * correctly).
 *
 * # Safety
 * `out` must point to `cap` writable bytes.
 */
size_t glove_proto_next_status(struct GloveProto *h, uint8_t *out, size_t cap);

/**
 * Last firmware-reported handedness: -1 unknown, 0 left, 1 right.
 * The caller compares against its own side (handedness is a firmware
 * precompile flag — a mismatch means the wrong glove is plugged in).
 *
 * # Safety
 * `h` must be null or a live handle from [`glove_proto_create`].
 */
int32_t glove_proto_handedness(const struct GloveProto *h);

/**
 * Begin a 100-frame baseline snapshot (mirrors
 * `FilterCommand::SnapshotBaseline`).
 *
 * # Safety
 * `h` must be null or a live handle from [`glove_proto_create`].
 */
void glove_proto_snapshot_baseline(const struct GloveProto *h);

/**
 * Clear the committed baseline (mirrors `FilterCommand::ClearBaseline`).
 *
 * # Safety
 * `h` must be null or a live handle from [`glove_proto_create`].
 */
void glove_proto_clear_baseline(const struct GloveProto *h);

/**
 * Enable (default) or disable this session's tactile filter. Enabled: `feed`
 * applies baseline subtraction + EMA + denoise in place, so the queued payload
 * and every decode are filtered. Disabled: taxels pass through raw. One mode
 * at a time — the choice flows through to the queued payload and every decode
 * alike. Reset by [`glove_proto_create`] (i.e. by a `Reset`), so
 * re-apply after reconnecting.
 *
 * # Safety
 * `h` must be null or a live handle from [`glove_proto_create`].
 */
void glove_proto_set_filter_enabled(struct GloveProto *h, bool enabled);

/**
 * Encode the StreamingMode command as serial-ready bytes: a leading 0x00
 * (flushes the firmware's COBS parser — send it on every (re)connect)
 * followed by the COBS-framed command. Returns bytes written.
 *
 * # Safety
 * `out` must point to `cap` writable bytes.
 */
size_t glove_proto_encode_streaming(bool enable, uint8_t *out, size_t cap);

/**
 * Encode the Ping heartbeat (COBS, serial-ready). Send it every 1 s to feed
 * the firmware watchdog. Returns bytes written.
 *
 * # Safety
 * `out` must point to `cap` writable bytes.
 */
size_t glove_proto_encode_ping(uint8_t *out, size_t cap);

/**
 * Encode the Pong heartbeat (plain postcard). Emit it after 2 s without
 * status messages, so a downstream consumer sees the link is alive. Returns
 * bytes written.
 *
 * # Safety
 * `out` must point to `cap` writable bytes.
 */
size_t glove_proto_encode_pong(uint8_t *out, size_t cap);

/**
 * Classify a status payload (one of the `GLOVE_PROTO_KIND_*` constants), or -1
 * if it doesn't decode.
 *
 * # Safety
 * `payload` must point to `len` valid bytes.
 */
int32_t glove_proto_status_kind(const uint8_t *payload, size_t len);

/**
 * Number of taxels in a flattened tactile frame (see
 * [`glove_proto_decode_tactile`]).
 */
size_t glove_proto_taxel_count(void);

/**
 * Physical taxel positions in millimetres for `hand` (0 = left, 1 = right),
 * written as x,y pairs in the same flat order as
 * [`glove_proto_decode_tactile`]. Returns the number of taxels written, or 0
 * when `cap` is smaller than `2 * glove_proto_taxel_count()`.
 *
 * The values come from the glove CAD drawing, so a viewer can lay the taxels
 * out in the shape of the hand rather than as an arbitrary grid. The origin
 * is the drawing's, y grows downwards, and the caller scales to its canvas.
 *
 * # Safety
 * `out_xy` must point to `cap` writable f32.
 */
size_t glove_proto_taxel_positions_mm(uint8_t hand, float *out_xy, size_t cap);

/**
 * Decode a `TactileStatus` payload into `out_taxels` ([`N_TAXELS`] × u16,
 * segment order t_dip..lower_palm — same order as the taxel mapping YAML).
 * Values are post-filter. Returns false for any other payload kind.
 *
 * # Safety
 * `payload` must point to `len` valid bytes; `out_taxels` to
 * [`glove_proto_taxel_count`] writable u16; `out_uid`/`out_timestamp` to
 * one writable u16 each (may be null to skip).
 */
bool glove_proto_decode_tactile(const uint8_t *payload, size_t len,
                                uint16_t *out_taxels, uint16_t *out_uid,
                                uint16_t *out_timestamp);

/**
 * Decode an `ImuStatus` payload into `out_quat` ([w, x, y, z] unit
 * quaternion). Returns false for any other payload kind.
 *
 * # Safety
 * `payload` must point to `len` valid bytes; `out_quat` to 4 writable f32;
 * `out_timestamp` to one writable u16 (may be null to skip).
 */
bool glove_proto_decode_imu(const uint8_t *payload, size_t len, float *out_quat,
                            uint16_t *out_timestamp);

#ifdef __cplusplus
} // extern "C"
#endif // __cplusplus

#endif /* GLOVE_PROTO_H */
