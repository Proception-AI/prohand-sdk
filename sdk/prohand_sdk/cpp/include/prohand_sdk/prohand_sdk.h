/*
 * ProHand Client SDK — C API
 *
 * GENERATED FILE — do not edit.
 * Regenerate with: just crates hand-client-sdk header
 *
 * Units are wire units. Rotary positions are raw FT3950 encoder counts
 * (0-4095, neutral 2048), not degrees. Linear positions are 0.01 mm. Joint
 * states are CompactJointState pairs: position in 0.01 degrees, velocity or
 * torque as a full-range int16 normalized to -1.0..1.0.
 *
 * State codes carried in ProHandStateInfo::code:
 *   rotary / linear (PROHAND_MSG_ROTARY_STATE, PROHAND_MSG_LINEAR_STATE)
 *     0 clear, 1 idle, 2 servicing, 3 configuring, 4 neutralizing, 5 scanning,
 *     6 ready, 7 running, 8 shutdown, 9 sleep, 10 all, 11 error (detail =
 *     servo error code), 12 thermal protection
 *   hand (PROHAND_MSG_HAND_STATE)
 *     0 idle, 1 sleep, 2 ready, 3 running (detail = streaming mode),
 *     4 servicing, 5 calibrating (detail = phase), 6 error (detail = hand
 *     error), 7 homing, 8 thermal protection
 *   imu (PROHAND_MSG_IMU_STATE)
 *     0 idle, 1 running, 2 calibrating, 3 error
 *   current sense (PROHAND_MSG_CURRENT_SENSE_STATE)
 *     0 idle, 1 running, 2 error
 */

#ifndef PROHAND_SDK_H
#define PROHAND_SDK_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#define SERVO_COUNT 16
#define LINEAR_COUNT 2

/**
 * Buckets in the sliding window. Each is one minimum-alert-interval wide, so a
 * signal repeating at the firmware maximum fills exactly one per bucket and
 * reads 100%.
 */
#define BUCKETS 12

/**
 * Distinct signal signatures tracked. Sized well above a real device: 16 rotary
 * + 2 linear + IMU across a handful of severities and codes.
 */
#define MAX_SIGNALS 48

#define INFO 0

#define WARNING 1

#define ERROR 2

/**
 * Host-side OTA chunk size, in bytes. Deliberately NOT
 * `OTA_MAX_CHUNK_SIZE`: that is a per-binary RECEIVE bound which feature
 * unification can raise to 96 in some hosts (proglove-messages enables
 * `prohand-config/esp32`), while other receivers (driver) stay at 64 —
 * mismatched senders get every chunk rejected. 64 fits every receiver.
 */
#define OTA_HOST_CHUNK_SIZE 64

/**
 * Reported before any `HandState` has been seen.
 */
#define HAND_STATE_UNKNOWN -1

/**
 * `hand_state` value for thermal lockdown — the authoritative signal, since
 * firmware puts the hand in this state whether or not an alert reaches us.
 */
#define HAND_STATE_THERMAL_PROTECTION 8

#define UNKNOWN 0

#define LEFT 1

#define RIGHT 2

#define PROHAND_MSG_NONE -1

#define PROHAND_MSG_PONG 0

#define PROHAND_MSG_HAND_REQUEST_ECHO 1

#define PROHAND_MSG_ROTARY_STATE 2

#define PROHAND_MSG_LINEAR_STATE 3

#define PROHAND_MSG_HAND_STATE 4

#define PROHAND_MSG_ROTARY_GRP_STATUS 5

#define PROHAND_MSG_LINEAR_GRP_STATUS 6

#define PROHAND_MSG_ROTARY_GRP_TARGET 7

#define PROHAND_MSG_LINEAR_GRP_TARGET 8

#define PROHAND_MSG_HANDEDNESS 9

#define PROHAND_MSG_IMU_STATUS 10

#define PROHAND_MSG_IMU_STATE 11

#define PROHAND_MSG_TIME_SYNC_ACK 12

#define PROHAND_MSG_ALERT 13

#define PROHAND_MSG_CURRENT_SENSE_STATUS 14

#define PROHAND_MSG_CURRENT_SENSE_STATE 15

#define PROHAND_MSG_HAND_JOINT_TARGET 16

#define PROHAND_MSG_WRIST_JOINT_TARGET 17

#define PROHAND_MSG_HAND_JOINT_STATUS 18

#define PROHAND_MSG_WRIST_JOINT_STATUS 19

#define PROHAND_MSG_ROTARY_SRV_STATUS 100

#define PROHAND_MSG_LINEAR_SRV_STATUS 101

#define PROHAND_MSG_OTA_STATUS 102

#define PROHAND_MSG_METADATA 103

#define PROHAND_MSG_CALIBRATION_RAMP_SAMPLE 104

#define PROHAND_MSG_CALIBRATION_TRIM 105

#define PROHAND_MSG_CALIBRATION_PROGRESS 106

#define PROHAND_MSG_POSITION_CORRECTION_SNAPSHOT 107

#define PROHAND_MSG_TX_DROP_REPORT 108

#define PROHAND_MSG_IMU_TUNING_CONFIG 109

#define PROHAND_MSG_IDENTITY_RESPONSE 110

#define PROHAND_CALIB_ABORT 0

#define PROHAND_CALIB_THUMB 1

#define PROHAND_CALIB_INDEX 2

#define PROHAND_CALIB_MIDDLE 4

#define PROHAND_CALIB_RING 8

#define PROHAND_CALIB_PINKY 16

#define PROHAND_CALIB_ALL 31

#define PROHAND_SUCCESS 0

#define PROHAND_ERROR_NULL -1

#define PROHAND_ERROR_CONNECTION -2

#define PROHAND_ERROR_INVALID_ARGUMENT -3

#define PROHAND_ERROR_NOT_CONNECTED -4

#define PROHAND_ERROR_UNSUPPORTED -5

#define PROHAND_ERROR_OTHER -99

/**
 * Result codes for FFI functions
 */
typedef enum ProHandResult {
  ProHandResult_Success = 0,
  ProHandResult_ErrorNull = -1,
  ProHandResult_ErrorConnection = -2,
  ProHandResult_ErrorInvalidArgument = -3,
  ProHandResult_ErrorNotConnected = -4,
  ProHandResult_ErrorUnsupported = -5,
  ProHandResult_ErrorOther = -99,
} ProHandResult;

/**
 * Which firmware subsystem emitted the alert.
 *
 * Encoded as bit values so multiple sources can be OR-combined into a single
 * `u8` mask in firmware state tracking (e.g. the hand task tracking which
 * subsystems are currently in thermal lockdown).
 */
enum AlertSource
#ifdef __cplusplus
    : uint8_t
#endif // __cplusplus
{
  AlertSource_Hand = (1 << 0),
  AlertSource_Rotary = (1 << 1),
  AlertSource_Linear = (1 << 2),
  AlertSource_Calibration = (1 << 3),
  AlertSource_Imu = (1 << 4),
  AlertSource_System = (1 << 5),
};
#ifndef __cplusplus
typedef uint8_t AlertSource;
#endif // __cplusplus

/**
 * How severe the alert is.
 */
enum AlertSeverity
#ifdef __cplusplus
    : uint8_t
#endif // __cplusplus
{
  /**
   * Informational — no action required.
   */
  AlertSeverity_Info = 0,
  /**
   * Degraded operation — calibration may continue but result may be affected.
   */
  AlertSeverity_Warning = 1,
  /**
   * Fatal for the current operation — firmware is about to return an error
   * state.
   */
  AlertSeverity_Error = 2,
};
#ifndef __cplusplus
typedef uint8_t AlertSeverity;
#endif // __cplusplus

/**
 * Stage of a thermal event, carried directly on `ProHandAlert::thermal_event`.
 *
 * `None` is the default for any alert that is not a thermal event. Thermal
 * alerts always set one of `Warning` / `Protection` / `Recovered`.
 */
enum ThermalEvent
#ifdef __cplusplus
    : uint8_t
#endif // __cplusplus
{
  /**
   * Not a thermal event — default for non-thermal alerts.
   */
  ThermalEvent_None = 0,
  /**
   * Subsystem crossed its warning temperature (alert-only, no lockdown).
   */
  ThermalEvent_Warning = 1,
  /**
   * Subsystem crossed its over-temperature threshold — hand is entering
   * `HandState::ThermalProtection`.
   */
  ThermalEvent_Protection = 2,
  /**
   * Subsystem cooled back below its recovery threshold — clears the
   * protection bit; hand returns to `Ready` once every subsystem clears.
   */
  ThermalEvent_Recovered = 3,
};
#ifndef __cplusplus
typedef uint8_t ThermalEvent;
#endif // __cplusplus

/**
 * What happened. Values are stable: they cross the C boundary.
 */
enum SystemEventKind
#ifdef __cplusplus
    : uint8_t
#endif // __cplusplus
{
  /**
   * A subsystem has been thermally warning long enough to be real, not noise.
   */
  SystemEventKind_ThermalWarningConfirmed = 0,
  /**
   * A confirmed warning has stopped recurring.
   */
  SystemEventKind_ThermalWarningCleared = 1,
  /**
   * The hand entered thermal lockdown. Never delayed or debounced.
   */
  SystemEventKind_ThermalLockdown = 2,
  /**
   * The hand came out of thermal lockdown.
   */
  SystemEventKind_ThermalRecovered = 3,
};
#ifndef __cplusplus
typedef uint8_t SystemEventKind;
#endif // __cplusplus

/**
 * Opaque handle to a ProHandIpcClient
 */
typedef struct ProHandClientHandle ProHandClientHandle;

/**
 * USB Device information (simplified - only what we can provide)
 */
typedef struct ProHandUsbDeviceInfo {
  const char *port_name;
  const char *display_name;
} ProHandUsbDeviceInfo;

/**
 * Rotary/linear positions and targets only. Superseded by
 * [`crate::ffi_message::ProHandMessage`], which covers every message kind.
 *
 * **One kind per call.** `status_type` says which of the four arrays was
 * filled; the other three are zero. Reading `rotary_targets` off a `status_type
 * == 1` frame yields zeroes, not the commanded target — that is this struct's
 * shape, not a missing target echo.
 */
typedef struct ProHandStatusInfo {
  int is_valid;
  /**
   * 0 unknown, 1 rotary status, 2 linear status, 3 rotary target, 4 linear
   * target.
   */
  int status_type;
  /**
   * Rotary feedback in raw FT3950 encoder counts, 0–4095 (neutral 2048).
   * Not degrees — the wire carries counts. Valid when `status_type == 1`.
   */
  short rotary_positions[16];
  /**
   * Linear feedback in 0.01 mm stroke counts. Valid when `status_type == 2`.
   */
  short linear_positions[2];
  /**
   * Commanded rotary targets in encoder counts. Valid when `status_type == 3`.
   */
  short rotary_targets[16];
  /**
   * Commanded linear targets in 0.01 mm counts. Valid when `status_type == 4`.
   */
  short linear_targets[2];
} ProHandStatusInfo;

/**
 * Thermal load for one `(source, actuator)`, reassembled from the two thermal
 * severities. Kept as a distinct type because the ProHand SDK hands it across
 * its C boundary verbatim.
 */
typedef struct ThermalLoad {
  /**
   * `AlertSource` bit value.
   */
  uint8_t source;
  /**
   * Actuator index, or `0xFF` when not actuator-specific.
   */
  uint8_t actuator;
  /**
   * Warning-severity thermal alerts as a percentage of the publishable
   * maximum. Saturates at 100.
   */
  uint8_t warning_percent;
  /**
   * Same, for thermal lockdown (error severity).
   */
  uint8_t lockdown_percent;
  uint16_t warning_count;
  uint16_t lockdown_count;
  /**
   * Temperature on the most recent thermal alert, °C.
   */
  int8_t last_temp_c;
  /**
   * Highest temperature seen since the tracker was created, °C.
   */
  int8_t peak_temp_c;
} ThermalLoad;

/**
 * Aggregate health of the connected hand.
 *
 * `repr(C)`: handed across the SDK's C boundary verbatim. Field order groups by
 * alignment so the layout has no interior padding to get wrong.
 */
typedef struct ProHandSystemStatus {
  /**
   * Milliseconds since the last status message of any kind, or `u64::MAX`
   * when none has arrived yet. Finer-grained liveness than `connected`,
   * which stays true for up to 10 s after the driver goes silent.
   */
  uint64_t ms_since_heartbeat;
  /**
   * Non-zero while the driver connection is live.
   */
  int connected;
  /**
   * Latest `HandState` code, or `-1` before one has been reported.
   */
  int hand_state;
  /**
   * Distinct alert signatures active in the window.
   */
  uint16_t active_signals;
  /**
   * Total alerts across all signatures in the window. Saturates at
   * `u16::MAX`; see `SharedThermalLoad::totals`.
   */
  uint16_t alerts_in_window;
  /**
   * `0` unknown, `1` left, `2` right.
   */
  uint8_t handedness;
  /**
   * Non-zero while a thermal lockdown is latched. A *state*, not a rate — it
   * does not age out of the window while the hand is still locked out.
   */
  uint8_t thermal_lockdown;
  /**
   * Worst subsystem's thermal warning rate, as a percentage of the maximum
   * firmware can publish. `0` when nothing is warm.
   */
  uint8_t worst_warning_percent;
  /**
   * Same, for thermal lockdown alerts.
   */
  uint8_t worst_lockdown_percent;
  /**
   * Actuator carrying that worst load; `0xFF` when none.
   */
  uint8_t worst_actuator;
  /**
   * Highest temperature on any thermal alert in the window, °C.
   */
  int8_t peak_temp_c;
  /**
   * Highest alert severity in the window: `0` info, `1` warning, `2` error.
   */
  uint8_t worst_severity;
} ProHandSystemStatus;

/**
 * One qualified event.
 *
 * `repr(C)`: handed across the C boundary verbatim, field order grouped by
 * alignment so there is no interior padding to get wrong.
 */
typedef struct ProHandSystemEvent {
  /**
   * Client monotonic milliseconds at which the event was raised.
   */
  uint64_t timestamp_ms;
  /**
   * Source-specific code from the triggering alert. `0` for thermal.
   */
  uint16_t code;
  /**
   * `detail` from the triggering alert — temperature in °C for thermal.
   */
  int16_t detail;
  /**
   * A [`SystemEventKind`].
   */
  uint8_t kind;
  /**
   * `AlertSource` bit value.
   */
  uint8_t source;
  /**
   * Actuator index, or `0xFF` when not actuator-specific.
   */
  uint8_t actuator;
  /**
   * `AlertSeverity` of the triggering alert.
   */
  uint8_t severity;
  /**
   * Warning rate for this subsystem when the event was raised, as a
   * percentage of the maximum firmware can publish.
   */
  uint8_t rate_percent;
} ProHandSystemEvent;

/**
 * Identity of a repeating alert. Two alerts share a rate only when all four
 * fields match.
 */
typedef struct SignalKey {
  /**
   * `AlertSource` bit value.
   */
  uint8_t source;
  /**
   * `AlertSeverity` value — see [`severity`].
   */
  uint8_t severity;
  /**
   * Actuator index, or `0xFF` when not actuator-specific.
   */
  uint8_t actuator;
  /**
   * Source-specific code. `0` for thermal alerts.
   */
  uint16_t code;
} SignalKey;

/**
 * One signal's rate over the window.
 */
typedef struct SignalRate {
  struct SignalKey key;
  /**
   * Alerts over the window as a percentage of the most firmware could
   * publish in it. Saturates at 100.
   */
  uint8_t rate_percent;
  uint16_t count_in_window;
  /**
   * `detail` from the most recent alert. Temperature in °C for thermal.
   */
  int16_t last_detail;
  /**
   * Highest `detail` seen since the tracker was created.
   */
  int16_t peak_detail;
  /**
   * Clock reading when this signature was first seen.
   */
  uint64_t first_seen_ms;
  /**
   * Clock reading of the most recent alert.
   */
  uint64_t last_seen_ms;
} SignalRate;

typedef struct RotaryStatus {
  int16_t position;
  int16_t velocity;
  uint16_t torque;
  uint8_t temperature;
  uint8_t voltage;
} RotaryStatus;

/**
 * Timestamped batch of all rotary servo statuses.
 * `timestamp_ms` is the firmware monotonic clock (same domain as `ImuStatus`)
 * captured immediately after the servo bus read loop completes.
 */
typedef struct RotaryStatusStamped {
  /**
   * Firmware monotonic timestamp in milliseconds when this batch was assembled.
   */
  uint32_t timestamp_ms;
  struct RotaryStatus servos[SERVO_COUNT];
} RotaryStatusStamped;

typedef struct RotaryCommand {
  int16_t position;
  uint16_t torque;
  uint8_t velocity;
} RotaryCommand;

/**
 * Timestamped batch of commanded rotary targets (echo).
 * `timestamp_ms` is when the firmware applied this command to the bus,
 * enabling precise command-to-response latency: `status.ts − target.ts`.
 */
typedef struct RotaryTargetStamped {
  uint32_t timestamp_ms;
  struct RotaryCommand commands[SERVO_COUNT];
} RotaryTargetStamped;

typedef struct LinearStatus {
  int16_t position;
  int16_t current;
  int16_t speed;
  uint16_t error;
  int16_t temp;
} LinearStatus;

/**
 * Timestamped batch of all linear actuator statuses.
 * `timestamp_ms` is the firmware monotonic clock (same domain as `ImuStatus`)
 * captured immediately after the linear bus read loop completes.
 */
typedef struct LinearStatusStamped {
  uint32_t timestamp_ms;
  struct LinearStatus actuators[LINEAR_COUNT];
} LinearStatusStamped;

typedef struct LinearCommand {
  int16_t position;
  uint16_t speed;
  uint8_t torque;
} LinearCommand;

/**
 * Timestamped batch of commanded linear targets (echo).
 */
typedef struct LinearTargetStamped {
  uint32_t timestamp_ms;
  struct LinearCommand commands[LINEAR_COUNT];
} LinearTargetStamped;

typedef struct CompactJointState {
  int16_t scaled_position;
  int16_t normalized_vel_or_tau;
} CompactJointState;

/**
 * Finger joint position command (one frame at a time).
 */
typedef struct HandCommand {
  /**
   * Monotonic sequence counter (wraps). Used to detect dropped frames.
   */
  uint16_t timestamp;
  uint16_t uid;
  struct CompactJointState thumb[4];
  struct CompactJointState index[4];
  struct CompactJointState middle[4];
  struct CompactJointState ring[4];
  struct CompactJointState pinky[4];
  /**
   * Global maximum servo velocity cap applied to all fingers.
   * `0` = use firmware `DEFAULT_VELOCITY`.
   */
  uint8_t velocity_saturation;
} HandCommand;

/**
 * Timestamped echo of a `HandCommand` accepted by the firmware.
 * `timestamp_ms` is the firmware monotonic time when the command was
 * consumed by the hand task — pair with `RotaryGrpStatus.timestamp_ms`
 * for command-to-response latency. `command.timestamp` is the host
 * sequence counter and remains untouched for drop detection.
 */
typedef struct HandJointTargetStamped {
  uint32_t timestamp_ms;
  struct HandCommand command;
} HandJointTargetStamped;

/**
 * Forward-kinematics estimate of finger joint state derived from the
 * rotary-bus feedback. `timestamp_ms` is the firmware monotonic time at FK
 * evaluation — pairs with `HandJointTarget.timestamp_ms` for command-vs-FK
 * tracking. Per-finger × per-joint shape mirrors `HandCommand` so host code
 * can index identically.
 */
typedef struct HandJointStatusStamped {
  uint32_t timestamp_ms;
  struct CompactJointState thumb[4];
  struct CompactJointState index[4];
  struct CompactJointState middle[4];
  struct CompactJointState ring[4];
  struct CompactJointState pinky[4];
} HandJointStatusStamped;

/**
 * Wrist joint position command.
 */
typedef struct WristCommand {
  uint16_t timestamp;
  uint16_t uid;
  struct CompactJointState wrist[2];
} WristCommand;

/**
 * Timestamped echo of a `WristCommand` accepted by the firmware.
 * See `HandJointTargetStamped` for the timestamp contract.
 */
typedef struct WristJointTargetStamped {
  uint32_t timestamp_ms;
  struct WristCommand command;
} WristJointTargetStamped;

/**
 * FK estimate of wrist joint state derived from the linear-actuator feedback.
 */
typedef struct WristJointStatusStamped {
  uint32_t timestamp_ms;
  struct CompactJointState wrist[2];
} WristJointStatusStamped;

typedef struct ImuStatus {
  /**
   * Firmware monotonic timestamp in milliseconds (wraps after ~49 days)
   */
  uint32_t timestamp_ms;
  float temp;
  float accel_x;
  float accel_y;
  float accel_z;
  float gyro_x;
  float gyro_y;
  float gyro_z;
  float qw;
  float qx;
  float qy;
  float qz;
} ImuStatus;

/**
 * INA219 sample.
 *
 * `timestamp_ms` is the firmware monotonic clock (same domain as `ImuStatus`).
 */
typedef struct CurrentSenseStatus {
  uint32_t timestamp_ms;
  /**
   * Bus voltage in millivolts. INA219 LSB = 4 mV.
   */
  uint16_t bus_voltage_mv;
  /**
   * Shunt voltage in microvolts. Signed (current direction).
   */
  int32_t shunt_uv;
  /**
   * Load current in milliamps. Sign matches shunt direction.
   */
  int16_t current_ma;
  /**
   * Power in milliwatts.
   */
  uint16_t power_mw;
} CurrentSenseStatus;

/**
 * Unified firmware diagnostic alert, emitted over USB instead of defmt.
 */
typedef struct ProHandAlert {
  /**
   * Firmware monotonic timestamp in milliseconds. `0` when unavailable.
   */
  uint32_t timestamp_ms;
  /**
   * Which subsystem raised the alert.
   */
  AlertSource source;
  /**
   * Severity level.
   */
  AlertSeverity severity;
  /**
   * Source-specific error code (see module-level doc for interpretation).
   * `0` for thermal alerts (the typed `thermal_event` and `source` already
   * carry the full meaning).
   */
  uint16_t code;
  /**
   * Actuator index the alert relates to; `NOT_APPLICABLE` (0xFF) when
   * not actuator-specific.
   */
  uint8_t actuator;
  /**
   * Extra context: servo mask, retry count, torque reading, stage id, etc.
   * For thermal alerts this carries the peak temperature in °C
   * (re-interpreted as `i16`).
   */
  uint16_t detail;
  /**
   * Thermal-event stage. `None` for any non-thermal alert; one of
   * `Warning` / `Protection` / `Recovered` when this is a thermal alert
   * emitted by an `is_thermal_capable` source (Rotary / Linear / Imu).
   */
  ThermalEvent thermal_event;
} ProHandAlert;
/**
 * Sentinel value for `actuator` meaning the alert is not tied to a
 * specific actuator (e.g. bus-wide errors, sensor alerts). Picked at
 * `0xFF` because actuator indices live in `0..SERVO_COUNT (16)`, so
 * any real index is far below this value.
 */
#define ProHandAlert_NOT_APPLICABLE 255

/**
 * Subsystem state transition — rotary, linear, hand, IMU or current sense.
 *
 * `ServoState` and `HandState` carry payloads on some variants, so they cannot
 * cross a C ABI as-is. `code` is the variant index and `detail` its payload:
 * the servo error code, the streaming mode, or the calibration phase. The
 * tables are in the generated header.
 */
typedef struct ProHandStateInfo {
  uint8_t code;
  uint8_t _pad;
  uint16_t detail;
} ProHandStateInfo;

/**
 * Only the arm named by [`ProHandMessage::kind`] is initialised.
 *
 * Every arm but [`Self::state`] and [`Self::handedness`] is a
 * `prohand-messages` type verbatim.
 */
typedef union ProHandMessagePayload {
  struct RotaryStatusStamped rotary_status;
  struct RotaryTargetStamped rotary_target;
  struct LinearStatusStamped linear_status;
  struct LinearTargetStamped linear_target;
  struct HandJointTargetStamped hand_joint_target;
  struct HandJointStatusStamped hand_joint_status;
  struct WristJointTargetStamped wrist_joint_target;
  struct WristJointStatusStamped wrist_joint_status;
  struct ImuStatus imu;
  struct CurrentSenseStatus power;
  struct ProHandAlert alert;
  struct ProHandStateInfo state;
  /**
   * 0 unknown, 1 left, 2 right.
   */
  uint8_t handedness;
  /**
   * Kinds reported by number only. Zeroed.
   */
  uint8_t raw[168];
} ProHandMessagePayload;

/**
 * One status message: its wire kind, its firmware timestamp, and its payload.
 */
typedef struct ProHandMessage {
  /**
   * A `PROHAND_MSG_*` value — the `ProHandStatus` discriminant.
   */
  int kind;
  /**
   * Firmware monotonic milliseconds, or 0 for kinds carrying no timestamp.
   * Also readable from the payload's own `timestamp_ms` where it has one.
   */
  uint32_t timestamp_ms;
  union ProHandMessagePayload payload;
} ProHandMessage;

/**
 * Size of every struct the FFI hands across the boundary, for load-time
 * verification by a language wrapper that declares the layout itself.
 */
typedef struct ProHandAbiSizes {
  uint32_t message;
  uint32_t payload;
  uint32_t rotary_status_stamped;
  uint32_t rotary_target_stamped;
  uint32_t linear_status_stamped;
  uint32_t linear_target_stamped;
  uint32_t hand_joint_target_stamped;
  uint32_t hand_joint_status_stamped;
  uint32_t wrist_joint_target_stamped;
  uint32_t wrist_joint_status_stamped;
  uint32_t imu_status;
  uint32_t current_sense_status;
  uint32_t alert;
  uint32_t state_info;
  uint32_t status_info;
  uint32_t thermal_load;
  uint32_t system_status;
} ProHandAbiSizes;

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

/**
 * Create a new ProHand IPC client with all endpoints
 *
 * # Parameters
 * - `command_endpoint`: ZeroMQ endpoint for commands (e.g.,
 * "tcp://127.0.0.1:5562")
 * - `status_endpoint`: ZeroMQ endpoint for status (e.g.,
 * "tcp://127.0.0.1:5561")
 * - `hand_streaming_endpoint`: ZeroMQ endpoint for hand streaming (e.g.,
 * "tcp://127.0.0.1:5563")
 * - `wrist_streaming_endpoint`: ZeroMQ endpoint for wrist streaming (e.g.,
 * "tcp://127.0.0.1:5564")
 *
 * # Returns
 * - Pointer to ProHandClientHandle on success, null on failure
 *
 * # Safety
 * The returned pointer must be freed with `prohand_client_destroy()`
 */
struct ProHandClientHandle *
prohand_client_create(const char *command_endpoint, const char *status_endpoint,
                      const char *hand_streaming_endpoint,
                      const char *wrist_streaming_endpoint);

/**
 * Destroy a ProHand client handle
 *
 * # Safety
 * The handle must have been created with `prohand_client_create()` and not
 * already freed
 */
void prohand_client_destroy(struct ProHandClientHandle *handle);

/**
 * Check if client is connected
 */
int prohand_client_is_connected(const struct ProHandClientHandle *handle);

/**
 * Milliseconds elapsed since the last status message arrived on the status
 * channel.
 *
 * Finer-grained than `prohand_client_is_connected()`, which stays true for up
 * to 10 s after the driver goes silent — this is the value that watchdog reads.
 * Writes `UINT64_MAX` when no status has arrived yet, matching the sentinel
 * `prohand_get_system_status()` uses for the same condition. Previously this
 * reported the client's own age, which was indistinguishable from a live
 * driver.
 *
 * # Parameters
 * - `out_ms`: Written with the elapsed milliseconds, or `UINT64_MAX` if none
 * yet
 */
enum ProHandResult
prohand_ms_since_last_heartbeat(const struct ProHandClientHandle *handle,
                                uint64_t *out_ms);

/**
 * Send a ping command
 */
enum ProHandResult prohand_send_ping(const struct ProHandClientHandle *handle);

/**
 * Enable or disable streaming mode
 */
enum ProHandResult
prohand_set_streaming_mode(const struct ProHandClientHandle *handle,
                           int enabled);

/**
 * Send rotary commands via REQ/REP command channel (16 motors)
 *
 * Uses the command socket (REQ/REP). For high-frequency commands, use
 * prohand_send_rotary_streams() instead.
 *
 * # Parameters
 * - `positions`: Array of 16 position values in radians
 * - `torques`: Array of 16 torque values (normalized 0.0 to 1.0)
 */
enum ProHandResult
prohand_send_rotary_commands(const struct ProHandClientHandle *handle,
                             const float *positions, const float *torques);

/**
 * Send rotary commands via PUB/SUB streaming channel (16 motors)
 *
 * Uses the streaming socket (PUB/SUB) for high-frequency commands.
 * Requires: Client created with streaming endpoint AND driver in streaming
 * mode.
 *
 * # Parameters
 * - `positions`: Array of 16 position values in radians
 * - `torques`: Array of 16 torque values (normalized 0.0 to 1.0)
 *
 * # Returns
 * - PROHAND_ERROR_NOT_CONNECTED if streaming endpoint was not provided at
 * client creation
 */
enum ProHandResult
prohand_send_rotary_streams(const struct ProHandClientHandle *handle,
                            const float *positions, const float *torques);

/**
 * Send linear commands via REQ/REP command channel (2 motors)
 *
 * Uses the command socket (REQ/REP). For high-frequency commands, use
 * prohand_send_linear_streams() instead.
 *
 * # Parameters
 * - `positions`: Array of 2 position values in radians
 * - `speeds`: Array of 2 speed values (normalized 0.0 to 1.0)
 */
enum ProHandResult
prohand_send_linear_commands(const struct ProHandClientHandle *handle,
                             const float *positions, const float *speeds);

/**
 * Send linear commands via PUB/SUB streaming channel (2 motors)
 *
 * Uses the streaming socket (PUB/SUB) for high-frequency commands.
 * Requires: Client created with streaming endpoint AND driver in streaming
 * mode.
 *
 * # Parameters
 * - `positions`: Array of 2 position values in radians
 * - `speeds`: Array of 2 speed values (normalized 0.0 to 1.0)
 *
 * # Returns
 * - PROHAND_ERROR_NOT_CONNECTED if streaming endpoint was not provided at
 * client creation
 */
enum ProHandResult
prohand_send_linear_streams(const struct ProHandClientHandle *handle,
                            const float *positions, const float *speeds);

/**
 * Perform zero calibration on selected joints
 *
 * # Parameters
 * - `mask`: Array of 16 boolean values (0 or 1) indicating which joints to
 * calibrate
 */
enum ProHandResult
prohand_send_zero_calibration(const struct ProHandClientHandle *handle,
                              const int *mask);

/**
 * Start or abort auto-calibration for the selected fingers.
 *
 * # Parameters
 * - `finger_mask`: Bitmask of fingers to calibrate — thumb 0x01, index 0x02,
 *   middle 0x04, ring 0x08, pinky 0x10. `0` aborts a running calibration.
 */
enum ProHandResult
prohand_send_auto_calibration(const struct ProHandClientHandle *handle,
                              uint8_t finger_mask);

/**
 * Start or abort the homing sequence.
 *
 * # Parameters
 * - `enabled`: Non-zero starts homing, zero aborts it
 */
enum ProHandResult prohand_send_homing(const struct ProHandClientHandle *handle,
                                       int enabled);

/**
 * Send hand command via REQ/REP command channel (high-level joint angles, uses
 * inverse kinematics)
 *
 * Uses the command socket (REQ/REP). For high-frequency commands, use
 * prohand_send_hand_streams() instead.
 *
 * This sends joint angles per finger, which the firmware processes through
 * inverse kinematics to compute actuator positions. This is the high-level API.
 *
 * # Parameters
 * - `positions`: Array of 20 floats (5 fingers × 4 joints) in radians
 *   Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
 * - `torques`: Array of 20 floats (normalized 0.0 to 1.0), one per joint, in
 *   the same order as `positions`. Pass the same value 20 times for a uniform
 *   grip; the firmware applies each independently.
 * - `velocity_saturation`: Global servo velocity cap, normalized 0.0 to 1.0.
 *   `0.0` uses the firmware default; the cap is per-hand, not per-finger.
 *
 * # Returns
 * - ProHandResult::Success on success
 * - ProHandResult::ErrorNull if handle, positions, or torques is null
 * - ProHandResult::ErrorOther on other errors
 */
enum ProHandResult
prohand_send_hand_command(const struct ProHandClientHandle *handle,
                          const float *positions, const float *torques,
                          float velocity_saturation);

/**
 * Send hand command via PUB/SUB streaming channel (high-level joint angles,
 * uses inverse kinematics)
 *
 * Uses the streaming socket (PUB/SUB) for high-frequency commands.
 * Requires: Client created with streaming endpoint AND driver in streaming
 * mode.
 *
 * This sends joint angles per finger, which the firmware processes through
 * inverse kinematics to compute actuator positions. This is the high-level API.
 *
 * # Parameters
 * - `positions`: Array of 20 floats (5 fingers × 4 joints) in radians
 *   Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
 * - `torques`: Array of 20 floats (normalized 0.0 to 1.0), one per joint, in
 *   the same order as `positions`. Pass the same value 20 times for a uniform
 *   grip; the firmware applies each independently.
 * - `velocity_saturation`: Global servo velocity cap, normalized 0.0 to 1.0.
 *   `0.0` uses the firmware default; the cap is per-hand, not per-finger.
 *
 * # Returns
 * - ProHandResult::Success on success
 * - ProHandResult::ErrorNull if handle, positions, or torques is null
 * - ProHandResult::ErrorNotConnected if streaming endpoint was not provided at
 * client creation
 * - ProHandResult::ErrorOther on other errors
 */
enum ProHandResult
prohand_send_hand_streams(const struct ProHandClientHandle *handle,
                          const float *positions, const float *torques,
                          float velocity_saturation);

/**
 * Send wrist command via REQ/REP command channel (wrist joint angles with
 * velocities)
 *
 * Uses the command socket (REQ/REP). For high-frequency commands, use
 * prohand_send_wrist_streams() instead.
 *
 * # Parameters
 * - `positions`: Array of 2 floats (wrist joints) in radians
 * - `use_profiler`: If true, runs the wrist motion profiler (position-only
 * profiling, commands max velocity). Velocities are always implicit [1.0, 1.0].
 */
enum ProHandResult
prohand_send_wrist_command(const struct ProHandClientHandle *handle,
                           const float *positions, bool use_profiler);

/**
 * Send wrist command via PUB/SUB streaming channel (wrist joint angles with
 * velocities)
 *
 * Uses the streaming socket (PUB/SUB) for high-frequency commands.
 * Requires: Client created with streaming endpoint AND driver in streaming
 * mode.
 *
 * # Parameters
 * - `positions`: Array of 2 floats (wrist joints) in radians
 * - `use_profiler`: If true, runs the wrist motion profiler (position-only
 * profiling, commands max velocity). Velocities are always implicit [1.0, 1.0].
 *
 * # Returns
 * - ProHandResult::Success on success
 * - ProHandResult::ErrorNull if handle or positions is null
 * - ProHandResult::ErrorNotConnected if streaming endpoint was not provided at
 * client creation
 * - ProHandResult::ErrorOther on other errors
 */
enum ProHandResult
prohand_send_wrist_streams(const struct ProHandClientHandle *handle,
                           const float *positions, bool use_profiler);

/**
 * Discover connected ProHand USB devices
 *
 * # Parameters
 * - `out_devices`: Output array to store device info
 * - `max_devices`: Maximum number of devices to return
 *
 * # Returns
 * Number of devices found, or negative error code
 */
int prohand_discover_usb_devices(struct ProHandUsbDeviceInfo *out_devices,
                                 int max_devices);

/**
 * Free a string allocated by the library
 */
void prohand_free_string(char *s);

/**
 * Try to receive status (non-blocking)
 *
 * # Parameters
 * - `out_status`: Output structure to fill with status data
 *
 * # Returns
 * 1 if status was received, 0 if no status available, negative on error
 */
int prohand_try_recv_status(const struct ProHandClientHandle *handle,
                            struct ProHandStatusInfo *out_status);

/**
 * Check if the driver is in Running state (streaming active)
 *
 * This polls the status channel and checks if RotaryState or LinearState
 * is in Running mode, which indicates streaming is active.
 *
 * # Returns
 * 1 if in running state, 0 if not, negative on error
 */
int prohand_is_running_state(const struct ProHandClientHandle *handle);

/**
 * Get library version string
 */
const char *prohand_get_version(void);

/**
 * Configure wrist motion limits (only active when motion-profiler feature is
 * enabled)
 */
enum ProHandResult
prohand_set_wrist_limits(const struct ProHandClientHandle *handle,
                         const float *max_velocity,
                         const float *max_acceleration, const float *max_jerk);

/**
 * Per-subsystem thermal load, as a percentage of the rate at which firmware
 * can publish thermal alerts.
 *
 * Firmware caps thermal alerts at one per subsystem per 5 s, so that ceiling
 * is the denominator: a lone temperature excursion reads single digits, a
 * genuinely hot actuator saturates the channel and reads 100. Prefer this over
 * reacting to individual warnings — one warning carries no severity, a
 * percentage does.
 *
 * Measured by the driver on its raw alert stream and republished on the
 * filtered status channel, so the debouncing applied to that channel does not
 * distort these numbers — and the counts span the driver's uptime, not just
 * this client's connection.
 *
 * # Parameters
 * - `out_loads`: caller-allocated array to fill
 * - `max_loads`: capacity of `out_loads`
 *
 * # Returns
 * - `>= 0`: number of subsystems written (quiet ones are omitted)
 * - `ProHandResult::ErrorNull` if either argument is null/zero
 */
int prohand_get_thermal_load(const struct ProHandClientHandle *handle,
                             struct ThermalLoad *out_loads, uint32_t max_loads);

/**
 * Worst subsystem's thermal load, ranked by lockdown then warning.
 *
 * The one-number readout: `warning_percent` and `lockdown_percent` on the
 * hottest subsystem. See `prohand_get_thermal_load()` for what the scale means.
 *
 * # Returns
 * - `1` when `out_load` was filled
 * - `0` when nothing has alerted inside the window
 * - `ProHandResult::ErrorNull` if either argument is null
 */
int prohand_get_worst_thermal_load(const struct ProHandClientHandle *handle,
                                   struct ThermalLoad *out_load);

/**
 * Aggregate health of the connected hand in one passive read.
 *
 * Liveness, hand state, handedness, thermal load and alert rates together —
 * the call to make when you want to know whether the hand is healthy, rather
 * than reacting to individual alerts. A lone alert carries no severity; a rate
 * and a latched lockdown state do.
 *
 * Assembled client-side from the driver's raw status stream. Nothing is added
 * to the wire for it, and reading it never consumes a status message or sends
 * a command, so it is safe to poll from a UI at frame rate.
 *
 * See `prohand_get_thermal_load()` for the per-subsystem breakdown behind
 * `worst_*`, and the header's hand-state table for `hand_state`.
 *
 * # Returns
 * - ProHandResult::Success on success
 * - ProHandResult::ErrorNull if handle or out_status is null
 */
enum ProHandResult
prohand_get_system_status(const struct ProHandClientHandle *handle,
                          struct ProHandSystemStatus *out_status);

/**
 * Take the next qualified monitoring event, oldest first.
 *
 * Events run *beside* the status stream, not in front of it: nothing is
 * filtered out of `prohand_try_recv_message()`, so a diagnostic tool still sees
 * every alert first-hand. An event says a condition has been *established* — a
 * thermal warning that persisted rather than a single noisy sample, or a
 * lockdown — which is the thing worth reacting to. A lone alert cannot express
 * that, which is how a stream of them came to read as a hardware fault.
 *
 * Poll until this returns 0 to drain the queue. Delivery is by polling rather
 * than a callback on purpose: a callback would fire from the SDK's receiver
 * thread, which for a managed-language wrapper means re-entering its runtime
 * from a foreign thread.
 *
 * # Returns
 * - `1` when `out_event` was filled
 * - `0` when the queue is empty
 * - `ProHandResult::ErrorNull` if either argument is null
 */
int prohand_poll_system_event(const struct ProHandClientHandle *handle,
                              struct ProHandSystemEvent *out_event);

/**
 * Number of monitoring events discarded because the queue filled.
 *
 * The queue is bounded and drops oldest-first, so a consumer that stops polling
 * costs a fixed amount of memory rather than growing without bound. A non-zero
 * count here means this client is not polling often enough.
 *
 * # Returns
 * - `>= 0`: events lost since the client was created
 * - `ProHandResult::ErrorNull` if handle is null
 */
int prohand_dropped_event_count(const struct ProHandClientHandle *handle);

/**
 * Every alerting signal active inside the window, thermal or not.
 *
 * The per-signature breakdown behind `system_status().active_signals`: one row
 * per unique `(source, severity, actuator, code)`, so a flapping servo error
 * and a thermal warning on the same actuator are separate rows rather than
 * pooled. `prohand_get_thermal_load()` is the thermal-only view of the same
 * data, reassembled per subsystem.
 *
 * `rate_percent` is the fraction of the maximum rate firmware can publish for
 * that signature — a lone excursion reads single digits, a persistent fault
 * saturates at 100.
 *
 * # Parameters
 * - `out_rates`: caller-allocated array to fill
 * - `max_rates`: capacity of `out_rates`
 *
 * # Returns
 * - `>= 0`: number of signals written (quiet ones are omitted)
 * - `ProHandResult::ErrorNull` if either argument is null/zero
 */
int prohand_get_signal_rates(const struct ProHandClientHandle *handle,
                             struct SignalRate *out_rates, uint32_t max_rates);

/**
 * Receive the next status message (non-blocking).
 *
 * Returns 1 when `out_message` was filled, 0 when nothing was queued, or a
 * negative [`ProHandResult`] on error. Read `out_message->kind` first and touch
 * only the payload arm it names.
 */
int prohand_try_recv_message(const struct ProHandClientHandle *handle,
                             struct ProHandMessage *out_message);

/**
 * Report the size of every struct crossing the FFI boundary.
 *
 * A wrapper that declares the layout itself (Python ctypes) compares these at
 * load time, so a dylib/wrapper mismatch fails immediately instead of silently
 * misreading every field.
 */
int prohand_abi_sizes(struct ProHandAbiSizes *out_sizes);

#ifdef __cplusplus
} // extern "C"
#endif // __cplusplus

#endif /* PROHAND_SDK_H */
