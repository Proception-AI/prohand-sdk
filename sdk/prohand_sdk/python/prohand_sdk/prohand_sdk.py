"""
ProHand Client SDK - Python Bindings

This module provides Python bindings for the ProHand Client SDK using ctypes.

Usage:
    from prohand_sdk import ProHandClient

    # Create client with all endpoints
    client = ProHandClient(
        "tcp://127.0.0.1:5562",  # Command endpoint
        "tcp://127.0.0.1:5561",  # Status endpoint
        "tcp://127.0.0.1:5563",   # Hand streaming endpoint
        "tcp://127.0.0.1:5564"    # Wrist streaming endpoint
    )

    # Check connection
    if client.is_connected():
        print("Connected to ProHand device")

    # Send commands via command channel
    positions = [0.0] * 16
    torques = [0.45] * 16
    client.send_rotary_commands(positions, torques)

    # Send commands via streaming channel (high-frequency)
    client.set_streaming_mode(True)
    client.wait_for_streaming_ready()
    client.send_rotary_streams(positions, torques)

    # Receive status
    status = client.try_recv_status()
    if status and status.is_valid:
        if status.status_type == 1:
            print(f"Rotary positions: {status.rotary_positions}")
        elif status.status_type == 2:
            print(f"Linear positions: {status.linear_positions}")

    # Clean up
    client.close()

Requirements:
    - Place the compiled library (libprohand_client_sdk.so/.dylib/.dll) in:
      - ../lib/ relative to this script (recommended shared location)
      - Same directory as this script (legacy)
      - System library path
      - Or set PROHAND_SDK_LIB environment variable
"""

import ctypes
import logging
import os
import sys
from ctypes import (
    POINTER,
    Union as CUnion,
    c_char,
    c_char_p,
    c_int,
    c_int8,
    c_int16,
    c_int32,
    c_float,
    c_short,
    c_bool,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    Structure,
    byref,
    pointer,
    string_at,
)
from typing import List, Optional, Union
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)


# ============================================================================
# LIBRARY LOADING
# ============================================================================


def _find_library():
    """Find the ProHand SDK library"""
    # Check environment variable first
    env_path = os.environ.get("PROHAND_SDK_LIB")
    if env_path and os.path.exists(env_path):
        return env_path

    # Determine library name based on platform and architecture
    import platform

    machine = platform.machine()

    if sys.platform == "darwin":
        lib_name = "libprohand_client_sdk.dylib"
    elif sys.platform == "win32":
        lib_name = "prohand_client_sdk.dll"
    elif sys.platform.startswith("linux"):
        # On aarch64 (Jetson Nano), use the _aarch64 variant
        if machine == "aarch64":
            lib_name = "libprohand_client_sdk_aarch64.so"
        elif machine in ("x86_64", "amd64", "i686", "i386"):
            lib_name = "libprohand_client_sdk.so"
        else:
            raise RuntimeError(
                f"Unsupported Linux architecture: {machine}. Supported architectures: x86_64, aarch64"
            )
    else:
        raise RuntimeError(
            f"Unsupported platform: {sys.platform}. Supported platforms: darwin, win32, linux"
        )

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Check in ../lib/ (shared library location)
    lib_path = os.path.join(script_dir, "..", "..", "lib", lib_name)
    if os.path.exists(lib_path):
        return lib_path

    # Try loading from system library path
    try:
        return lib_name
    except Exception:
        raise RuntimeError(
            f"Could not find ProHand SDK library. "
            f"Expected '{lib_name}' in:\n"
            f"  - {os.path.join(script_dir, '..', '..', 'lib')}\n"
            f"  - System library path\n"
            f"  - Or set PROHAND_SDK_LIB environment variable"
        )


# Load the library
_lib_path = _find_library()
_lib = ctypes.CDLL(_lib_path)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class ProHandResult(IntEnum):
    """Result codes returned by SDK functions"""

    SUCCESS = 0
    ERROR_NULL = -1
    ERROR_CONNECTION = -2
    ERROR_INVALID_ARGUMENT = -3
    ERROR_NOT_CONNECTED = -4
    ERROR_UNSUPPORTED = -5
    ERROR_OTHER = -99


class CalibrationMask(IntEnum):
    """Finger bitmask values for send_auto_calibration(). OR them together."""

    ABORT = 0b00000
    THUMB = 0b00001
    INDEX = 0b00010
    MIDDLE = 0b00100
    RING = 0b01000
    PINKY = 0b10000
    ALL = 0b11111


# ============================================================================
# STRUCTURES
# ============================================================================


class ProHandClientHandle(Structure):
    """Opaque handle to ProHand client (do not instantiate directly)"""

    pass


class ProHandUsbDeviceInfo(Structure):
    """USB device information"""

    # POINTER(c_char), not c_char_p: ctypes converts a c_char_p field to bytes on
    # read, discarding the original pointer. Freeing that would hand
    # prohand_free_string a pointer into Python's heap, which aborts the process.
    # Read these with string_at() and free the pointer itself.
    _fields_ = [
        ("port_name", POINTER(c_char)),
        ("display_name", POINTER(c_char)),
    ]


class ProHandStatusInfo(Structure):
    """Hand status information"""

    _fields_ = [
        ("is_valid", c_int),
        ("status_type", c_int),
        ("rotary_positions", c_short * 16),
        ("linear_positions", c_short * 2),
        ("rotary_targets", c_short * 16),
        ("linear_targets", c_short * 2),
    ]


# ============================================================================
# STATUS MESSAGES — ctypes mirrors of the prohand-messages wire structs
#
# These layouts must match the Rust `repr(C)` structs exactly. `_check_abi()`
# below verifies that against the loaded library at import time, so a wrapper
# built against a different dylib fails loudly instead of misreading fields.
# ============================================================================

ROTARY_COUNT = 16
LINEAR_COUNT = 2
JOINT_COUNT = 20
WRIST_JOINT_COUNT = 2


class MessageKind(IntEnum):
    """Wire discriminant of `ProHandStatus`. Values are the protocol's, not ours."""

    NONE = -1
    PONG = 0
    HAND_REQUEST_ECHO = 1
    ROTARY_STATE = 2
    LINEAR_STATE = 3
    HAND_STATE = 4
    ROTARY_GRP_STATUS = 5
    LINEAR_GRP_STATUS = 6
    ROTARY_GRP_TARGET = 7
    LINEAR_GRP_TARGET = 8
    HANDEDNESS = 9
    IMU_STATUS = 10
    IMU_STATE = 11
    TIME_SYNC_ACK = 12
    ALERT = 13
    CURRENT_SENSE_STATUS = 14
    CURRENT_SENSE_STATE = 15
    HAND_JOINT_TARGET = 16
    WRIST_JOINT_TARGET = 17
    HAND_JOINT_STATUS = 18
    WRIST_JOINT_STATUS = 19
    # Host-synthesized per-signal alert rate. Consumed into the thermal-load
    # cache inside the dylib; read it with thermal_load(), not try_recv_message().
    HEALTH_STATUS = 20
    # Service side — reported by kind, payload not exposed here.
    ROTARY_SRV_STATUS = 100
    LINEAR_SRV_STATUS = 101
    OTA_STATUS = 102
    METADATA = 103
    CALIBRATION_RAMP_SAMPLE = 104
    CALIBRATION_TRIM = 105
    CALIBRATION_PROGRESS = 106
    POSITION_CORRECTION_SNAPSHOT = 107
    TX_DROP_REPORT = 108
    IMU_TUNING_CONFIG = 109
    IDENTITY_RESPONSE = 110


class AlertSource(IntEnum):
    HAND = 1
    ROTARY = 2
    LINEAR = 4
    CALIBRATION = 8
    IMU = 16
    SYSTEM = 32


class AlertSeverity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2


class ThermalEvent(IntEnum):
    NONE = 0
    WARNING = 1
    PROTECTION = 2
    RECOVERED = 3


class Handedness(IntEnum):
    UNKNOWN = 0
    LEFT = 1
    RIGHT = 2


class _RotaryStatusC(Structure):
    _fields_ = [
        ("position", c_short),
        ("velocity", c_short),
        ("torque", c_uint16),
        ("temperature", c_uint8),
        ("voltage", c_uint8),
    ]


class _RotaryCommandC(Structure):
    _fields_ = [("position", c_short), ("torque", c_uint16), ("velocity", c_uint8)]


class _RotaryStatusStampedC(Structure):
    _fields_ = [("timestamp_ms", c_uint32), ("servos", _RotaryStatusC * ROTARY_COUNT)]


class _RotaryTargetStampedC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("commands", _RotaryCommandC * ROTARY_COUNT),
    ]


class _LinearStatusC(Structure):
    _fields_ = [
        ("position", c_short),
        ("current", c_short),
        ("speed", c_short),
        ("error", c_uint16),
        ("temp", c_short),
    ]


class _LinearCommandC(Structure):
    _fields_ = [("position", c_short), ("speed", c_uint16), ("torque", c_uint8)]


class _LinearStatusStampedC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("actuators", _LinearStatusC * LINEAR_COUNT),
    ]


class _LinearTargetStampedC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("commands", _LinearCommandC * LINEAR_COUNT),
    ]


class _CompactJointStateC(Structure):
    """Wire-packed joint state: 0.01° position, i16-normalized velocity/torque."""

    _fields_ = [("scaled_position", c_short), ("normalized_vel_or_tau", c_short)]


class _HandCommandC(Structure):
    _fields_ = [
        ("sequence", c_uint16),
        ("uid", c_uint16),
        ("thumb", _CompactJointStateC * 4),
        ("index", _CompactJointStateC * 4),
        ("middle", _CompactJointStateC * 4),
        ("ring", _CompactJointStateC * 4),
        ("pinky", _CompactJointStateC * 4),
        ("velocity_saturation", c_uint8),
    ]


class _WristCommandC(Structure):
    _fields_ = [
        ("sequence", c_uint16),
        ("uid", c_uint16),
        ("wrist", _CompactJointStateC * WRIST_JOINT_COUNT),
    ]


class _HandJointTargetStampedC(Structure):
    _fields_ = [("timestamp_ms", c_uint32), ("command", _HandCommandC)]


class _HandJointStatusStampedC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("thumb", _CompactJointStateC * 4),
        ("index", _CompactJointStateC * 4),
        ("middle", _CompactJointStateC * 4),
        ("ring", _CompactJointStateC * 4),
        ("pinky", _CompactJointStateC * 4),
    ]


class _WristJointTargetStampedC(Structure):
    _fields_ = [("timestamp_ms", c_uint32), ("command", _WristCommandC)]


class _WristJointStatusStampedC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("wrist", _CompactJointStateC * WRIST_JOINT_COUNT),
    ]


class _ImuStatusC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("temp", c_float),
        ("accel_x", c_float),
        ("accel_y", c_float),
        ("accel_z", c_float),
        ("gyro_x", c_float),
        ("gyro_y", c_float),
        ("gyro_z", c_float),
        ("qw", c_float),
        ("qx", c_float),
        ("qy", c_float),
        ("qz", c_float),
    ]


class _CurrentSenseStatusC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("bus_voltage_mv", c_uint16),
        ("shunt_uv", ctypes.c_int32),
        ("current_ma", c_short),
        ("power_mw", c_uint16),
    ]


class _AlertC(Structure):
    _fields_ = [
        ("timestamp_ms", c_uint32),
        ("source", c_uint8),
        ("severity", c_uint8),
        ("code", c_uint16),
        ("actuator", c_uint8),
        ("detail", c_uint16),
        ("thermal_event", c_uint8),
    ]


class _StateInfoC(Structure):
    _fields_ = [("code", c_uint8), ("_pad", c_uint8), ("detail", c_uint16)]


class _MessagePayloadC(CUnion):
    _fields_ = [
        ("rotary_status", _RotaryStatusStampedC),
        ("rotary_target", _RotaryTargetStampedC),
        ("linear_status", _LinearStatusStampedC),
        ("linear_target", _LinearTargetStampedC),
        ("hand_joint_target", _HandJointTargetStampedC),
        ("hand_joint_status", _HandJointStatusStampedC),
        ("wrist_joint_target", _WristJointTargetStampedC),
        ("wrist_joint_status", _WristJointStatusStampedC),
        ("imu", _ImuStatusC),
        ("power", _CurrentSenseStatusC),
        ("alert", _AlertC),
        ("state", _StateInfoC),
        ("handedness", c_uint8),
        ("raw", c_uint8 * 168),
    ]


class ProHandMessageC(Structure):
    """Raw FFI message. Use `ProHandClient.try_recv_message()` for typed frames."""

    _fields_ = [
        ("kind", c_int32),
        ("timestamp_ms", c_uint32),
        ("payload", _MessagePayloadC),
    ]


class ThermalLoadC(Structure):
    """Mirror of the C `ThermalLoad`. Sizes checked by `_check_abi()`."""

    _fields_ = [
        ("source", c_uint8),
        ("actuator", c_uint8),
        ("warning_percent", c_uint8),
        ("lockdown_percent", c_uint8),
        ("warning_count", c_uint16),
        ("lockdown_count", c_uint16),
        ("last_temp_c", c_int8),
        ("peak_temp_c", c_int8),
    ]


class SignalKeyC(Structure):
    """Mirror of the C `SignalKey`."""

    _fields_ = [
        ("source", c_uint8),
        ("severity", c_uint8),
        ("actuator", c_uint8),
        ("code", c_uint16),
    ]


class SignalRateC(Structure):
    """Mirror of the C `SignalRate`."""

    _fields_ = [
        ("key", SignalKeyC),
        ("rate_percent", c_uint8),
        ("count_in_window", c_uint16),
        ("last_detail", c_int16),
        ("peak_detail", c_int16),
        ("first_seen_ms", c_uint64),
        ("last_seen_ms", c_uint64),
    ]


class ProHandSystemEventC(Structure):
    """Mirror of the C `ProHandSystemEvent`."""

    _fields_ = [
        ("timestamp_ms", c_uint64),
        ("code", c_uint16),
        ("detail", c_int16),
        ("kind", c_uint8),
        ("source", c_uint8),
        ("actuator", c_uint8),
        ("severity", c_uint8),
        ("rate_percent", c_uint8),
    ]


class ProHandSystemStatusC(Structure):
    """Mirror of the C `ProHandSystemStatus`. Size checked by `_check_abi()`."""

    _fields_ = [
        ("ms_since_heartbeat", c_uint64),
        ("connected", c_int),
        ("hand_state", c_int),
        ("active_signals", c_uint16),
        ("alerts_in_window", c_uint16),
        ("handedness", c_uint8),
        ("thermal_lockdown", c_uint8),
        ("worst_warning_percent", c_uint8),
        ("worst_lockdown_percent", c_uint8),
        ("worst_actuator", c_uint8),
        ("peak_temp_c", c_int8),
        ("worst_severity", c_uint8),
    ]


class ProHandAbiSizes(Structure):
    _fields_ = [
        ("message", c_uint32),
        ("payload", c_uint32),
        ("rotary_status_stamped", c_uint32),
        ("rotary_target_stamped", c_uint32),
        ("linear_status_stamped", c_uint32),
        ("linear_target_stamped", c_uint32),
        ("hand_joint_target_stamped", c_uint32),
        ("hand_joint_status_stamped", c_uint32),
        ("wrist_joint_target_stamped", c_uint32),
        ("wrist_joint_status_stamped", c_uint32),
        ("imu_status", c_uint32),
        ("current_sense_status", c_uint32),
        ("alert", c_uint32),
        ("state_info", c_uint32),
        ("status_info", c_uint32),
        ("thermal_load", c_uint32),
        ("system_status", c_uint32),
    ]


# ============================================================================
# TYPED FRAMES — one class per message kind, so no field can be misread
# ============================================================================

# Wire scaling: CompactJointState packs position as 0.01° and velocity/torque
# as a full-range i16. Converted here, once, for every Python consumer.
_CENTIDEG_TO_RAD = 3.141592653589793 / 18000.0
_NORMALIZED_SCALE = 1.0 / 32767.0


@dataclass
class RotaryStatusFrame:
    """Rotary servo feedback. Positions are raw FT3950 counts (0–4095, neutral 2048)."""

    timestamp_ms: int
    positions: List[int]
    velocities: List[int]
    torques: List[int]  # 0–1000
    temperatures_c: List[int]
    voltages: List[int]  # 0.1 V units


@dataclass
class RotaryTargetFrame:
    """Commanded rotary targets, as applied to the bus. Counts, torque cap, velocity cap."""

    timestamp_ms: int
    positions: List[int]
    torque_caps: List[int]
    velocity_caps: List[int]


@dataclass
class LinearStatusFrame:
    """Linear actuator feedback. Positions in 0.01 mm."""

    timestamp_ms: int
    positions: List[int]
    currents_ma: List[int]
    speeds: List[int]
    errors: List[int]
    temperatures_c: List[int]


@dataclass
class LinearTargetFrame:
    timestamp_ms: int
    positions: List[int]
    speed_caps: List[int]


@dataclass
class JointFrame:
    """Joint-space frame in real units: radians, plus normalized velocity/torque.

    `is_target` distinguishes the firmware's echo of an accepted command from its
    forward-kinematics feedback. `sequence`/`uid`/`velocity_saturation` are zero on
    a feedback frame.
    """

    timestamp_ms: int
    positions_rad: List[float]
    vel_or_tau: List[float]
    is_target: bool
    is_wrist: bool
    sequence: int = 0
    uid: int = 0
    velocity_saturation: int = 0


@dataclass
class ImuFrame:
    timestamp_ms: int
    accel_mps2: List[float]
    gyro_rps: List[float]
    quaternion_wxyz: List[float]
    temperature_c: float


@dataclass
class PowerFrame:
    timestamp_ms: int
    bus_voltage_mv: int
    shunt_uv: int
    current_ma: int
    power_mw: int


@dataclass
class AlertFrame:
    """Firmware warning. Interpret `code` by `source` — see the SDK README."""

    timestamp_ms: int
    source: AlertSource
    severity: AlertSeverity
    code: int
    detail: int
    actuator: Optional[int]  # None when not actuator-specific
    thermal_event: ThermalEvent


@dataclass
class StateFrame:
    """Subsystem state transition: rotary, linear, hand, IMU or current sense."""

    kind: MessageKind
    code: int
    detail: int


@dataclass
class HandednessFrame:
    handedness: Handedness


@dataclass
class OtherFrame:
    """A kind the typed API does not decode — service replies, clock sync, echoes."""

    kind: MessageKind
    timestamp_ms: int


class SystemEventKind(IntEnum):
    """What a `SystemEvent` reports."""

    #: A subsystem has been thermally warning long enough to be real, not noise.
    THERMAL_WARNING_CONFIRMED = 0
    #: A confirmed warning has stopped recurring.
    THERMAL_WARNING_CLEARED = 1
    #: The hand entered thermal lockdown. Never delayed or debounced.
    THERMAL_LOCKDOWN = 2
    #: The hand came out of thermal lockdown.
    THERMAL_RECOVERED = 3


@dataclass
class SystemEvent:
    """One qualified monitoring event.

    Events run *beside* the status stream, not in front of it — nothing is
    filtered out of `try_recv_status()`. An event says a condition has been
    established, which is what you can act on; a lone alert cannot express that.
    """

    timestamp_ms: int
    kind: SystemEventKind
    source: int
    actuator: int
    severity: int
    code: int
    #: Temperature in °C for thermal events.
    detail: int
    rate_percent: int


@dataclass
class SystemStatus:
    """Aggregate health of the hand — one passive read.

    Prefer this over reacting to individual alerts: a lone alert carries no
    severity, while a rate and a latched lockdown state do.

    Assembled client-side from the driver's raw status stream. Reading it never
    consumes a status message or sends a command, so it is safe to poll from a
    UI at frame rate.
    """

    ms_since_heartbeat: int
    connected: bool
    #: Hand-state code, or -1 before the device has reported one. See the
    #: hand-state table in prohand_sdk.h.
    hand_state: int
    active_signals: int
    alerts_in_window: int
    #: 0 unknown, 1 left, 2 right.
    handedness: int
    thermal_lockdown: bool
    worst_warning_percent: int
    worst_lockdown_percent: int
    #: Actuator carrying the worst thermal load; 0xFF when none.
    worst_actuator: int
    peak_temp_c: int
    #: 0 info, 1 warning, 2 error.
    worst_severity: int


@dataclass
class SignalRate:
    """One alerting signature and how hard it is firing.

    The per-signature breakdown behind `SystemStatus.active_signals`. A flapping
    servo error and a thermal warning on the same actuator are separate rows,
    not pooled. `thermal_load()` is the thermal-only view of the same data.
    """

    #: AlertSource bit value.
    source: int
    #: 0 info, 1 warning, 2 error.
    severity: int
    #: Actuator index, or 0xFF when not actuator-specific.
    actuator: int
    #: Source-specific code; 0 for thermal.
    code: int
    #: Alerts over the window as a % of the maximum publishable. Saturates at 100.
    rate_percent: int
    count_in_window: int
    #: Temperature in °C for thermal signals.
    last_detail: int
    peak_detail: int
    first_seen_ms: int
    last_seen_ms: int


@dataclass
class ThermalLoad:
    """One subsystem's thermal load over the rolling window.

    Firmware caps thermal alerts at one per subsystem per 5s, so that ceiling is
    the denominator: `warning_percent` is how much of it the subsystem actually
    used. A lone temperature excursion reads single digits; a genuinely hot
    actuator saturates the channel and reads 100.

    Prefer this over reacting to individual warnings — one warning carries no
    severity, a percentage does.
    """

    source: int
    actuator: int
    warning_percent: int
    lockdown_percent: int
    warning_count: int
    lockdown_count: int
    last_temp_c: int
    peak_temp_c: int


@dataclass
class UsbDevice:
    """Python-friendly USB device info"""

    port_name: str
    display_name: str


@dataclass
class HandStatus:
    """Rotary/linear positions and targets. Superseded by the typed frames from
    ProHandClient.try_recv_message(), which cover every message kind.

    Only the list matching `status_type` holds data on any given read; the others
    are zero. Values are raw wire units, not degrees.
    """

    is_valid: bool
    status_type: (
        int  # 1=rotary status, 2=linear status, 3=rotary target, 4=linear target
    )
    rotary_positions: List[int]  # FT3950 encoder counts, 0–4095 (neutral 2048)
    linear_positions: List[int]  # 0.01 mm stroke counts
    rotary_targets: List[int]  # commanded encoder counts
    linear_targets: List[int]  # commanded 0.01 mm counts


# ============================================================================
# FUNCTION SIGNATURES
# ============================================================================

# Client lifecycle
_lib.prohand_client_create.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
_lib.prohand_client_create.restype = POINTER(ProHandClientHandle)

_lib.prohand_client_destroy.argtypes = [POINTER(ProHandClientHandle)]
_lib.prohand_client_destroy.restype = None

_lib.prohand_client_is_connected.argtypes = [POINTER(ProHandClientHandle)]
_lib.prohand_client_is_connected.restype = c_int

_lib.prohand_ms_since_last_heartbeat.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_uint64),  # out_ms
]
_lib.prohand_ms_since_last_heartbeat.restype = c_int

# Commands
_lib.prohand_send_ping.argtypes = [POINTER(ProHandClientHandle)]
_lib.prohand_send_ping.restype = c_int

_lib.prohand_set_streaming_mode.argtypes = [POINTER(ProHandClientHandle), c_int]
_lib.prohand_set_streaming_mode.restype = c_int

_lib.prohand_send_rotary_commands.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),
    POINTER(c_float),
]
_lib.prohand_send_rotary_commands.restype = c_int

_lib.prohand_send_rotary_streams.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),
    POINTER(c_float),
]
_lib.prohand_send_rotary_streams.restype = c_int

_lib.prohand_send_linear_commands.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),
    POINTER(c_float),
]
_lib.prohand_send_linear_commands.restype = c_int

_lib.prohand_send_linear_streams.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),
    POINTER(c_float),
]
_lib.prohand_send_linear_streams.restype = c_int

# Wrist command (high-level wrist joints) - REQ/REP and streaming channels
_lib.prohand_send_wrist_command.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),  # 2 positions (wrist joints)
    c_bool,  # use_profiler
]
_lib.prohand_send_wrist_command.restype = c_int

_lib.prohand_send_wrist_streams.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),  # 2 positions (wrist joints)
    c_bool,  # use_profiler
]
_lib.prohand_send_wrist_streams.restype = c_int

# Wrist limits (optional; works only if motion profiler enabled in the build)
_lib.prohand_set_wrist_limits.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),  # max_velocity[2]
    POINTER(c_float),  # max_acceleration[2]
    POINTER(c_float),  # max_jerk[2]
]
_lib.prohand_set_wrist_limits.restype = c_int


# Thermal load readout
_lib.prohand_get_thermal_load.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(ThermalLoadC),
    c_uint32,
]
_lib.prohand_get_thermal_load.restype = c_int

_lib.prohand_get_worst_thermal_load.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(ThermalLoadC),
]
_lib.prohand_get_worst_thermal_load.restype = c_int

# Aggregate system status
_lib.prohand_get_system_status.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(ProHandSystemStatusC),
]
_lib.prohand_get_system_status.restype = c_int

# Event-driven monitoring
_lib.prohand_poll_system_event.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(ProHandSystemEventC),
]
_lib.prohand_poll_system_event.restype = c_int

_lib.prohand_dropped_event_count.argtypes = [POINTER(ProHandClientHandle)]
_lib.prohand_dropped_event_count.restype = c_int

# Per-signature alert rates
_lib.prohand_get_signal_rates.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(SignalRateC),
    c_uint32,
]
_lib.prohand_get_signal_rates.restype = c_int

# Hand command (high-level joint angles) - REQ/REP command channel
_lib.prohand_send_hand_command.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),  # 20 positions (5 fingers × 4 joints)
    POINTER(c_float),  # 20 torques, one per joint
    c_float,  # velocity_saturation, normalized 0.0-1.0 (0.0 = firmware default)
]
_lib.prohand_send_hand_command.restype = c_int

# Hand command (high-level joint angles) - PUB/SUB streaming channel
_lib.prohand_send_hand_streams.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_float),  # 20 positions (5 fingers × 4 joints)
    POINTER(c_float),  # 20 torques, one per joint
    c_float,  # velocity_saturation, normalized 0.0-1.0 (0.0 = firmware default)
]
_lib.prohand_send_hand_streams.restype = c_int

_lib.prohand_send_zero_calibration.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(c_int),
]
_lib.prohand_send_zero_calibration.restype = c_int

_lib.prohand_send_auto_calibration.argtypes = [
    POINTER(ProHandClientHandle),
    c_uint8,  # finger_mask
]
_lib.prohand_send_auto_calibration.restype = c_int

_lib.prohand_send_homing.argtypes = [POINTER(ProHandClientHandle), c_int]
_lib.prohand_send_homing.restype = c_int

# USB discovery
_lib.prohand_discover_usb_devices.argtypes = [POINTER(ProHandUsbDeviceInfo), c_int]
_lib.prohand_discover_usb_devices.restype = c_int

_lib.prohand_free_string.argtypes = [POINTER(c_char)]
_lib.prohand_free_string.restype = None

# Status polling
try:
    _lib.prohand_try_recv_message.argtypes = [
        POINTER(ProHandClientHandle),
        POINTER(ProHandMessageC),
    ]
    _lib.prohand_try_recv_message.restype = c_int

    _lib.prohand_abi_sizes.argtypes = [POINTER(ProHandAbiSizes)]
    _lib.prohand_abi_sizes.restype = c_int
except AttributeError as e:
    raise RuntimeError(
        f"{_lib_path} predates this wrapper — it has no {e.name}. "
        "Rebuild the SDK: just crates hand-client-sdk build-sdk"
    ) from e

_lib.prohand_try_recv_status.argtypes = [
    POINTER(ProHandClientHandle),
    POINTER(ProHandStatusInfo),
]
_lib.prohand_try_recv_status.restype = c_int

_lib.prohand_is_running_state.argtypes = [POINTER(ProHandClientHandle)]
_lib.prohand_is_running_state.restype = c_int

# Version
_lib.prohand_get_version.argtypes = []
_lib.prohand_get_version.restype = c_char_p


# ============================================================================
# EXCEPTIONS
# ============================================================================


class ProHandError(Exception):
    """Base exception for ProHand SDK errors"""

    pass


class ConnectionError(ProHandError):
    """Connection-related errors"""

    pass


class InvalidArgumentError(ProHandError):
    """Invalid argument errors"""

    pass


def _check_abi() -> None:
    """Verify the ctypes layouts above against the loaded library.

    The layouts are declared twice — here and in Rust — so a wrapper paired with a
    different dylib would silently misread every field. The library reports its
    own sizes; a mismatch raises at import instead.
    """
    sizes = ProHandAbiSizes()
    if _lib.prohand_abi_sizes(byref(sizes)) != ProHandResult.SUCCESS:
        raise RuntimeError("prohand_abi_sizes failed")

    expected = {
        "message": ProHandMessageC,
        "payload": _MessagePayloadC,
        "rotary_status_stamped": _RotaryStatusStampedC,
        "rotary_target_stamped": _RotaryTargetStampedC,
        "linear_status_stamped": _LinearStatusStampedC,
        "linear_target_stamped": _LinearTargetStampedC,
        "hand_joint_target_stamped": _HandJointTargetStampedC,
        "hand_joint_status_stamped": _HandJointStatusStampedC,
        "wrist_joint_target_stamped": _WristJointTargetStampedC,
        "wrist_joint_status_stamped": _WristJointStatusStampedC,
        "imu_status": _ImuStatusC,
        "current_sense_status": _CurrentSenseStatusC,
        "alert": _AlertC,
        "state_info": _StateInfoC,
        "status_info": ProHandStatusInfo,
        "thermal_load": ThermalLoadC,
        "system_status": ProHandSystemStatusC,
    }
    mismatches = [
        f"{name}: library {getattr(sizes, name)} != wrapper {ctypes.sizeof(struct)}"
        for name, struct in expected.items()
        if getattr(sizes, name) != ctypes.sizeof(struct)
    ]
    if mismatches:
        raise RuntimeError(
            "ProHand SDK ABI mismatch between this wrapper and "
            f"{_lib_path} — rebuild both:\n  " + "\n  ".join(mismatches)
        )


_check_abi()


def _joints_to_rad(states) -> tuple:
    """(positions_rad, vel_or_tau) from a sequence of packed CompactJointStates."""
    return (
        [state.scaled_position * _CENTIDEG_TO_RAD for state in states],
        [state.normalized_vel_or_tau * _NORMALIZED_SCALE for state in states],
    )


def _decode_message(message: ProHandMessageC):
    """Turn a raw FFI message into the typed frame for its kind."""
    kind = MessageKind(message.kind)
    payload = message.payload

    if kind == MessageKind.ROTARY_GRP_STATUS:
        servos = payload.rotary_status.servos
        return RotaryStatusFrame(
            timestamp_ms=payload.rotary_status.timestamp_ms,
            positions=[s.position for s in servos],
            velocities=[s.velocity for s in servos],
            torques=[s.torque for s in servos],
            temperatures_c=[s.temperature for s in servos],
            voltages=[s.voltage for s in servos],
        )
    if kind == MessageKind.ROTARY_GRP_TARGET:
        commands = payload.rotary_target.commands
        return RotaryTargetFrame(
            timestamp_ms=payload.rotary_target.timestamp_ms,
            positions=[c.position for c in commands],
            torque_caps=[c.torque for c in commands],
            velocity_caps=[c.velocity for c in commands],
        )
    if kind == MessageKind.LINEAR_GRP_STATUS:
        actuators = payload.linear_status.actuators
        return LinearStatusFrame(
            timestamp_ms=payload.linear_status.timestamp_ms,
            positions=[a.position for a in actuators],
            currents_ma=[a.current for a in actuators],
            speeds=[a.speed for a in actuators],
            errors=[a.error for a in actuators],
            temperatures_c=[a.temp for a in actuators],
        )
    if kind == MessageKind.LINEAR_GRP_TARGET:
        commands = payload.linear_target.commands
        return LinearTargetFrame(
            timestamp_ms=payload.linear_target.timestamp_ms,
            positions=[c.position for c in commands],
            speed_caps=[c.speed for c in commands],
        )
    if kind == MessageKind.HAND_JOINT_TARGET:
        command = payload.hand_joint_target.command
        states = [
            state
            for finger in (
                command.thumb,
                command.index,
                command.middle,
                command.ring,
                command.pinky,
            )
            for state in finger
        ]
        positions, vel_or_tau = _joints_to_rad(states)
        return JointFrame(
            timestamp_ms=payload.hand_joint_target.timestamp_ms,
            positions_rad=positions,
            vel_or_tau=vel_or_tau,
            is_target=True,
            is_wrist=False,
            sequence=command.sequence,
            uid=command.uid,
            velocity_saturation=command.velocity_saturation,
        )
    if kind == MessageKind.HAND_JOINT_STATUS:
        status = payload.hand_joint_status
        states = [
            state
            for finger in (
                status.thumb,
                status.index,
                status.middle,
                status.ring,
                status.pinky,
            )
            for state in finger
        ]
        positions, vel_or_tau = _joints_to_rad(states)
        return JointFrame(
            timestamp_ms=status.timestamp_ms,
            positions_rad=positions,
            vel_or_tau=vel_or_tau,
            is_target=False,
            is_wrist=False,
        )
    if kind == MessageKind.WRIST_JOINT_TARGET:
        command = payload.wrist_joint_target.command
        positions, vel_or_tau = _joints_to_rad(command.wrist)
        return JointFrame(
            timestamp_ms=payload.wrist_joint_target.timestamp_ms,
            positions_rad=positions,
            vel_or_tau=vel_or_tau,
            is_target=True,
            is_wrist=True,
            sequence=command.sequence,
            uid=command.uid,
        )
    if kind == MessageKind.WRIST_JOINT_STATUS:
        status = payload.wrist_joint_status
        positions, vel_or_tau = _joints_to_rad(status.wrist)
        return JointFrame(
            timestamp_ms=status.timestamp_ms,
            positions_rad=positions,
            vel_or_tau=vel_or_tau,
            is_target=False,
            is_wrist=True,
        )
    if kind == MessageKind.IMU_STATUS:
        imu = payload.imu
        return ImuFrame(
            timestamp_ms=imu.timestamp_ms,
            accel_mps2=[imu.accel_x, imu.accel_y, imu.accel_z],
            gyro_rps=[imu.gyro_x, imu.gyro_y, imu.gyro_z],
            quaternion_wxyz=[imu.qw, imu.qx, imu.qy, imu.qz],
            temperature_c=imu.temp,
        )
    if kind == MessageKind.CURRENT_SENSE_STATUS:
        power = payload.power
        return PowerFrame(
            timestamp_ms=power.timestamp_ms,
            bus_voltage_mv=power.bus_voltage_mv,
            shunt_uv=power.shunt_uv,
            current_ma=power.current_ma,
            power_mw=power.power_mw,
        )
    if kind == MessageKind.ALERT:
        alert = payload.alert
        return AlertFrame(
            timestamp_ms=alert.timestamp_ms,
            source=AlertSource(alert.source),
            severity=AlertSeverity(alert.severity),
            code=alert.code,
            detail=alert.detail,
            actuator=None if alert.actuator == 0xFF else alert.actuator,
            thermal_event=ThermalEvent(alert.thermal_event),
        )
    if kind in (
        MessageKind.ROTARY_STATE,
        MessageKind.LINEAR_STATE,
        MessageKind.HAND_STATE,
        MessageKind.IMU_STATE,
        MessageKind.CURRENT_SENSE_STATE,
    ):
        return StateFrame(
            kind=kind, code=payload.state.code, detail=payload.state.detail
        )
    if kind == MessageKind.HANDEDNESS:
        return HandednessFrame(handedness=Handedness(payload.handedness))

    return OtherFrame(kind=kind, timestamp_ms=message.timestamp_ms)


# Matches MAX_SIGNALS in the SDK's signal_rate tracker — the hard bound on how
# many rows either getter can return, so a buffer this size can never truncate.
MAX_SIGNALS = 48


def _system_event_from_c(c: "ProHandSystemEventC") -> SystemEvent:
    return SystemEvent(
        timestamp_ms=c.timestamp_ms,
        kind=SystemEventKind(c.kind),
        source=c.source,
        actuator=c.actuator,
        severity=c.severity,
        code=c.code,
        detail=c.detail,
        rate_percent=c.rate_percent,
    )


def _system_status_from_c(c: "ProHandSystemStatusC") -> SystemStatus:
    return SystemStatus(
        ms_since_heartbeat=c.ms_since_heartbeat,
        connected=bool(c.connected),
        hand_state=c.hand_state,
        active_signals=c.active_signals,
        alerts_in_window=c.alerts_in_window,
        handedness=c.handedness,
        thermal_lockdown=bool(c.thermal_lockdown),
        worst_warning_percent=c.worst_warning_percent,
        worst_lockdown_percent=c.worst_lockdown_percent,
        worst_actuator=c.worst_actuator,
        peak_temp_c=c.peak_temp_c,
        worst_severity=c.worst_severity,
    )


def _signal_rate_from_c(c: "SignalRateC") -> SignalRate:
    return SignalRate(
        source=c.key.source,
        severity=c.key.severity,
        actuator=c.key.actuator,
        code=c.key.code,
        rate_percent=c.rate_percent,
        count_in_window=c.count_in_window,
        last_detail=c.last_detail,
        peak_detail=c.peak_detail,
        first_seen_ms=c.first_seen_ms,
        last_seen_ms=c.last_seen_ms,
    )


def _thermal_load_from_c(c: "ThermalLoadC") -> ThermalLoad:
    return ThermalLoad(
        source=c.source,
        actuator=c.actuator,
        warning_percent=c.warning_percent,
        lockdown_percent=c.lockdown_percent,
        warning_count=c.warning_count,
        lockdown_count=c.lockdown_count,
        last_temp_c=c.last_temp_c,
        peak_temp_c=c.peak_temp_c,
    )


def _expand_torques(torque: Union[float, List[float]]):
    """Expand a torque argument into the 20 per-joint values the wire carries.

    Accepts a scalar (whole hand), 5 values (per finger, thumb to pinky), or 20
    (per joint, in the same order as positions).
    """
    if isinstance(torque, (int, float)):
        values = [float(torque)] * 20
    else:
        values = [float(t) for t in torque]
        if len(values) == 5:
            values = [values[i // 4] for i in range(20)]  # 4 joints per finger
        elif len(values) != 20:
            raise InvalidArgumentError(
                "torque must be a scalar, 5 values (per finger) or 20 (per joint), "
                f"got {len(values)}"
            )
    return (c_float * 20)(*values)


def _check_velocity_saturation(velocity_saturation: float) -> None:
    if not 0.0 <= velocity_saturation <= 1.0:
        raise InvalidArgumentError(
            "velocity_saturation is normalized 0.0-1.0 (0.0 = firmware default); "
            f"got {velocity_saturation}"
        )


def _check_result(result: int, operation: str = "operation"):
    """Check result code and raise exception if error"""
    if result == ProHandResult.SUCCESS:
        return
    elif result == ProHandResult.ERROR_NULL:
        raise ProHandError(f"{operation}: Null pointer error")
    elif result == ProHandResult.ERROR_CONNECTION:
        raise ConnectionError(f"{operation}: Connection error")
    elif result == ProHandResult.ERROR_INVALID_ARGUMENT:
        raise InvalidArgumentError(f"{operation}: Invalid argument")
    elif result == ProHandResult.ERROR_NOT_CONNECTED:
        raise ConnectionError(f"{operation}: Not connected")
    elif result == ProHandResult.ERROR_UNSUPPORTED:
        raise ProHandError(
            f"{operation}: Feature not supported (may be disabled in build)"
        )
    else:
        raise ProHandError(f"{operation}: Unknown error ({result})")


# ============================================================================
# HIGH-LEVEL PYTHON API
# ============================================================================


class ProHandClient:
    """
    ProHand Client SDK - Python Interface

    This class provides a high-level Python interface to the ProHand device.
    """

    def __init__(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
    ):
        """
        Create a new ProHand client

        Args:
            command_endpoint: ZeroMQ endpoint for commands (e.g., "tcp://127.0.0.1:5562")
            status_endpoint: ZeroMQ endpoint for status (e.g., "tcp://127.0.0.1:5561")
            hand_streaming_endpoint: ZeroMQ endpoint for hand streaming (e.g., "tcp://127.0.0.1:5563")
            wrist_streaming_endpoint: ZeroMQ endpoint for wrist streaming (e.g., "tcp://127.0.0.1:5564")

        Raises:
            ConnectionError: If connection fails
        """
        cmd_bytes = command_endpoint.encode("utf-8")
        status_bytes = status_endpoint.encode("utf-8")
        hand_streaming_bytes = hand_streaming_endpoint.encode("utf-8")
        wrist_streaming_bytes = wrist_streaming_endpoint.encode("utf-8")

        self._handle = _lib.prohand_client_create(
            cmd_bytes, status_bytes, hand_streaming_bytes, wrist_streaming_bytes
        )

        if not self._handle:
            raise ConnectionError("Failed to create ProHand client")

        self._closed = False

    def __del__(self):
        """Clean up resources"""
        self.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def close(self):
        """Close the client and free resources"""
        if not self._closed and self._handle:
            _lib.prohand_client_destroy(self._handle)
            self._handle = None
            self._closed = True

    def is_connected(self) -> bool:
        """Check if connected to device"""
        if self._closed:
            return False
        return bool(_lib.prohand_client_is_connected(self._handle))

    def ms_since_last_heartbeat(self) -> int:
        """
        Milliseconds elapsed since the last status message arrived.

        Finer-grained liveness than is_connected(), which stays True for up to
        10 seconds after the driver goes silent — this is the value that watchdog
        reads. Poll it to detect a stalled driver sooner.

        Returns 2**64 - 1 until the first status actually arrives, the same
        sentinel system_status().ms_since_heartbeat uses. It exceeds any timeout
        you compare it against, so a watchdog correctly reads "down"; special-case
        it before feeding the value to an average or a plot.

        Returns:
            Age of the last status message in milliseconds, or 2**64 - 1 if none

        Example:
            if client.ms_since_last_heartbeat() > 500:
                # Driver has gone quiet — stop commanding motion.
                ...
        """
        out_ms = c_uint64(0)
        result = _lib.prohand_ms_since_last_heartbeat(self._handle, byref(out_ms))
        _check_result(result, "ms_since_last_heartbeat")
        return out_ms.value

    # ========================================================================
    # COMMAND METHODS
    # ========================================================================

    def send_ping(self):
        """Send a ping command"""
        result = _lib.prohand_send_ping(self._handle)
        _check_result(result, "send_ping")

    def set_streaming_mode(self, enabled: bool):
        """Enable or disable streaming mode"""
        result = _lib.prohand_set_streaming_mode(self._handle, int(enabled))
        _check_result(result, "set_streaming_mode")

    def is_running_state(self) -> bool:
        """
        Check if the driver is in Running state (streaming active)

        Polls the status channel and checks if RotaryState or LinearState
        is in Running mode, which indicates streaming is truly active.

        Returns:
            True if in running state, False otherwise
        """
        result = _lib.prohand_is_running_state(self._handle)
        return result == 1

    def wait_for_streaming_ready(
        self, timeout: float = 1.0, retry_interval: float = 0.3
    ) -> bool:
        """
        Wait for streaming connection to be established with state verification

        This method repeatedly sends set_streaming_mode(True) and polls for
        Running state until confirmed or timeout.

        Args:
            timeout: Maximum time to wait in seconds (default: 1.0)
            retry_interval: How often to retry set_streaming_mode in seconds (default: 0.3)

        Returns:
            True if ready and in Running state, False if timeout

        Example:
            client.set_streaming_mode(True)
            if client.wait_for_streaming_ready():
                # Driver is confirmed in Running state
                client.send_rotary_streams(positions, torques)
        """
        import time

        # First, verify command channel is working
        try:
            self.send_ping()
        except Exception:
            logger.debug("Ping failed during enable_streaming_mode")
            return False

        start_time = time.time()
        last_retry_time = start_time
        poll_interval = 0.05  # Poll every 50ms

        # Initial delay for ZMQ PUB/SUB connection to establish
        time.sleep(0.2)

        # Keep retrying set_streaming_mode until Running state is detected
        while (time.time() - start_time) < timeout:
            # Check if driver reports Running state
            if self.is_running_state():
                return True

            # Retry set_streaming_mode if enough time has passed
            elapsed_since_retry = time.time() - last_retry_time
            if elapsed_since_retry >= retry_interval:
                try:
                    self.set_streaming_mode(True)
                    last_retry_time = time.time()
                except Exception:
                    logger.debug("set_streaming_mode retry failed, will keep trying")

            # Wait before next poll
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                time.sleep(min(poll_interval, remaining))
            else:
                break

        # Timeout - check one last time
        return self.is_running_state()

    def send_rotary_commands(self, positions: List[float], torques: List[float]):
        """
        Send rotary motor commands via REQ/REP command channel

        Uses the command socket. Not suitable for high-frequency control.
        For high-frequency commands, use send_rotary_streams() instead.

        Args:
            positions: List of 16 position values in radians
            torques: List of 16 torque values (normalized 0.0 to 1.0)
        """
        if len(positions) != 16 or len(torques) != 16:
            raise InvalidArgumentError("positions and torques must have 16 elements")

        pos_array = (c_float * 16)(*positions)
        torque_array = (c_float * 16)(*torques)

        result = _lib.prohand_send_rotary_commands(
            self._handle, pos_array, torque_array
        )
        _check_result(result, "send_rotary_commands")

    def send_rotary_streams(self, positions: List[float], torques: List[float]):
        """
        Send rotary motor commands via PUB/SUB streaming channel

        Uses the streaming socket for high-frequency control (100+ Hz).
        Requires: Client created with streaming endpoint AND driver in streaming mode.

        Args:
            positions: List of 16 position values in radians
            torques: List of 16 torque values (normalized 0.0 to 1.0)

        Raises:
            ConnectionError: If streaming endpoint was not provided or driver not in streaming mode
        """
        if len(positions) != 16 or len(torques) != 16:
            raise InvalidArgumentError("positions and torques must have 16 elements")

        pos_array = (c_float * 16)(*positions)
        torque_array = (c_float * 16)(*torques)

        result = _lib.prohand_send_rotary_streams(self._handle, pos_array, torque_array)
        _check_result(result, "send_rotary_streams")

    def send_linear_commands(self, positions: List[float], speeds: List[float]):
        """
        Send linear motor commands via REQ/REP command channel

        Uses the command socket. For high-frequency commands, use
        send_linear_streams() instead.

        Args:
            positions: List of 2 position values in radians
            speeds: List of 2 speed values (normalized 0.0 to 1.0)
        """
        if len(positions) != 2 or len(speeds) != 2:
            raise InvalidArgumentError("positions and speeds must have 2 elements")

        pos_array = (c_float * 2)(*positions)
        vel_array = (c_float * 2)(*speeds)

        result = _lib.prohand_send_linear_commands(self._handle, pos_array, vel_array)
        _check_result(result, "send_linear_commands")

    def send_linear_streams(self, positions: List[float], speeds: List[float]):
        """
        Send linear motor commands via PUB/SUB streaming channel

        Uses the streaming socket for high-frequency control.
        Requires: Client created with streaming endpoint AND driver in streaming mode.

        Args:
            positions: List of 2 position values in radians
            speeds: List of 2 speed values (normalized 0.0 to 1.0)

        Raises:
            ConnectionError: If streaming endpoint was not provided or driver not in streaming mode
        """
        if len(positions) != 2 or len(speeds) != 2:
            raise InvalidArgumentError("positions and speeds must have 2 elements")

        pos_array = (c_float * 2)(*positions)
        vel_array = (c_float * 2)(*speeds)

        result = _lib.prohand_send_linear_streams(self._handle, pos_array, vel_array)
        _check_result(result, "send_linear_streams")

    def send_wrist_command(self, positions: List[float], use_profiler: bool = False):
        """
        Send wrist joint command via REQ/REP command channel (high-level wrist joints)

        Uses the command socket. For high-frequency commands, use
        send_wrist_streams() instead.

        Args:
            positions: List of 2 wrist joint angles in radians
            use_profiler: Whether to enable wrist motion profiling (position-only, implicit max velocity)
        """
        if len(positions) != 2:
            raise InvalidArgumentError("positions must have 2 elements")
        pos_array = (c_float * 2)(*positions)
        if use_profiler:
            result = _lib.prohand_send_wrist_command(self._handle, pos_array, True)
        else:
            result = _lib.prohand_send_wrist_command(self._handle, pos_array, False)
        _check_result(result, "send_wrist_command")

    def send_wrist_streams(self, positions: List[float], use_profiler: bool = False):
        """
        Send wrist joint command via PUB/SUB streaming channel (high-level wrist joints)

        Uses the streaming socket for high-frequency control.
        Requires: Client created with streaming endpoint AND driver in streaming mode.

        Args:
            positions: List of 2 wrist joint angles in radians
            use_profiler: Whether to enable wrist motion profiling (position-only, implicit max velocity)
        """
        if len(positions) != 2:
            raise InvalidArgumentError("positions must have 2 elements")
        pos_array = (c_float * 2)(*positions)
        if use_profiler:
            result = _lib.prohand_send_wrist_streams(self._handle, pos_array, True)
        else:
            result = _lib.prohand_send_wrist_streams(self._handle, pos_array, False)
        _check_result(result, "send_wrist_streams")

    def set_wrist_limits(
        self,
        max_velocity: List[float],
        max_acceleration: List[float],
        max_jerk: List[float],
    ):
        """
        Configure wrist motion limits (rad units). Effective only if the SDK was built with the motion profiler feature.
        """
        if len(max_velocity) != 2 or len(max_acceleration) != 2 or len(max_jerk) != 2:
            raise InvalidArgumentError("wrist limits must have 2 elements each")
        vel = (c_float * 2)(*max_velocity)
        acc = (c_float * 2)(*max_acceleration)
        jerk = (c_float * 2)(*max_jerk)
        result = _lib.prohand_set_wrist_limits(self._handle, vel, acc, jerk)
        _check_result(result, "set_wrist_limits")

    def poll_event(self) -> Optional[SystemEvent]:
        """
        Take the next qualified monitoring event, oldest first, or None when the
        queue is empty.

        Events run beside the status stream, not in front of it: nothing is
        filtered out of `try_recv_message()`. Poll until this returns None to
        drain the queue.
        """
        out = ProHandSystemEventC()
        n = _lib.prohand_poll_system_event(self._handle, byref(out))
        if n < 0:
            _check_result(n, "poll_event")
        return _system_event_from_c(out) if n == 1 else None

    def drain_events(self) -> List[SystemEvent]:
        """Every queued monitoring event, oldest first."""
        events = []
        while (event := self.poll_event()) is not None:
            events.append(event)
        return events

    @property
    def dropped_events(self) -> int:
        """
        Events discarded because the queue filled — non-zero means this client
        is not polling often enough. The queue is bounded and drops oldest-first,
        so falling behind costs a fixed amount of memory, not unbounded growth.
        """
        n = _lib.prohand_dropped_event_count(self._handle)
        if n < 0:
            _check_result(n, "dropped_events")
        return n

    def system_status(self) -> SystemStatus:
        """
        Aggregate health of the hand: liveness, state, thermal load and alert
        rates in one passive read.

        Prefer this over reacting to individual alerts — a lone alert carries no
        severity, a rate and a latched lockdown state do.

        Never consumes a status message or sends a command, so it is safe to
        poll from a UI at frame rate.
        """
        out = ProHandSystemStatusC()
        result = _lib.prohand_get_system_status(self._handle, byref(out))
        _check_result(result, "system_status")
        return _system_status_from_c(out)

    def signal_rates(self) -> List[SignalRate]:
        """
        Every alerting signal active inside the window, thermal or not.

        One row per unique (source, severity, actuator, code). `thermal_load()`
        is the thermal-only view of the same data, reassembled per subsystem.
        """
        buf = (SignalRateC * MAX_SIGNALS)()
        n = _lib.prohand_get_signal_rates(self._handle, buf, c_uint32(MAX_SIGNALS))
        if n < 0:
            _check_result(n, "signal_rates")
        return [_signal_rate_from_c(buf[i]) for i in range(max(n, 0))]

    def thermal_load(self) -> List[ThermalLoad]:
        """
        Thermal load per subsystem, as a percentage of the maximum rate at which
        firmware can publish thermal alerts. Quiet subsystems are omitted.

        Measured by the driver on its raw alert stream and republished on the
        filtered status channel this client subscribes to, so the debouncing
        applied to that channel does not distort these numbers — and the counts
        span the driver's uptime, not just this connection.
        """
        buf = (ThermalLoadC * MAX_SIGNALS)()
        n = _lib.prohand_get_thermal_load(self._handle, buf, c_uint32(MAX_SIGNALS))
        _check_result(n, "thermal_load") if n < 0 else None
        return [_thermal_load_from_c(buf[i]) for i in range(max(n, 0))]

    def worst_thermal_load(self) -> Optional[ThermalLoad]:
        """
        The most loaded subsystem, lockdown ranked above warning.

        Returns None when nothing has alerted inside the window.
        """
        out = ThermalLoadC()
        n = _lib.prohand_get_worst_thermal_load(self._handle, byref(out))
        if n < 0:
            _check_result(n, "worst_thermal_load")
        return _thermal_load_from_c(out) if n == 1 else None

    def send_hand_command(
        self,
        positions: List[float],
        torque: Union[float, List[float]] = 0.45,
        velocity_saturation: float = 0.0,
    ):
        """
        Send hand command via REQ/REP command channel (high-level joint angles, uses inverse kinematics)

        Uses the command socket. For high-frequency commands, use
        send_hand_streams() instead.

        This sends joint angles per finger, which the firmware processes through
        inverse kinematics to compute actuator positions. This is the high-level API.

        Args:
            positions: List of 20 floats (5 fingers × 4 joints) in radians
                      Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
            torque: Torque normalized 0.0 to 1.0. A scalar applies to the whole
                      hand, 5 values apply per finger (thumb to pinky), and 20
                      apply per joint, in the same order as positions.
            velocity_saturation: Global servo velocity cap, normalized 0.0 to 1.0.
                      0.0 uses the firmware default. The cap is per-hand: the wire
                      carries one value for all fingers.

        Example:
            # Uniform grip
            positions = [0.0] * 20
            client.send_hand_command(positions, 0.45)

            # Light thumb, firm index, default elsewhere
            client.send_hand_command(positions, [0.2, 0.6, 0.45, 0.45, 0.45])
        """
        if len(positions) != 20:
            raise InvalidArgumentError(
                "positions must have 20 elements (5 fingers × 4 joints)"
            )
        _check_velocity_saturation(velocity_saturation)

        pos_array = (c_float * 20)(*positions)
        result = _lib.prohand_send_hand_command(
            self._handle,
            pos_array,
            _expand_torques(torque),
            c_float(velocity_saturation),
        )
        _check_result(result, "send_hand_command")

    def send_hand_streams(
        self,
        positions: List[float],
        torque: Union[float, List[float]] = 0.45,
        velocity_saturation: float = 0.0,
    ):
        """
        Send hand command via PUB/SUB streaming channel (high-level joint angles, uses inverse kinematics)

        Uses the streaming socket for high-frequency control.
        Requires: Client created with streaming endpoint AND driver in streaming mode.

        This sends joint angles per finger, which the firmware processes through
        inverse kinematics to compute actuator positions. This is the high-level API.

        Args:
            positions: List of 20 floats (5 fingers × 4 joints) in radians
                      Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
            torque: Torque normalized 0.0 to 1.0. A scalar applies to the whole
                      hand, 5 values apply per finger (thumb to pinky), and 20
                      apply per joint, in the same order as positions.
            velocity_saturation: Global servo velocity cap, normalized 0.0 to 1.0.
                      0.0 uses the firmware default. The cap is per-hand: the wire
                      carries one value for all fingers.

        Raises:
            ConnectionError: If streaming endpoint was not provided or driver not in streaming mode

        Example:
            # Setup
            client.set_streaming_mode(True)
            client.wait_for_streaming_ready()

            # High-frequency loop
            for _ in range(100):
                positions = [0.0] * 20
                positions[4] = math.radians(30.0)  # index metacarpal
                client.send_hand_streams(positions, 0.45)
        """
        if len(positions) != 20:
            raise InvalidArgumentError(
                "positions must have 20 elements (5 fingers × 4 joints)"
            )
        _check_velocity_saturation(velocity_saturation)

        pos_array = (c_float * 20)(*positions)
        result = _lib.prohand_send_hand_streams(
            self._handle,
            pos_array,
            _expand_torques(torque),
            c_float(velocity_saturation),
        )
        _check_result(result, "send_hand_streams")

    def send_zero_calibration(self, mask: List[bool]):
        """
        Perform zero calibration on selected joints

        Args:
            mask: List of 16 boolean values indicating which joints to calibrate
        """
        if len(mask) != 16:
            raise InvalidArgumentError("mask must have 16 elements")

        mask_array = (c_int * 16)(*[int(b) for b in mask])
        result = _lib.prohand_send_zero_calibration(self._handle, mask_array)
        _check_result(result, "send_zero_calibration")

    def send_auto_calibration(self, finger_mask: int = CalibrationMask.ALL):
        """
        Start or abort auto-calibration for the selected fingers

        Drives each selected finger against its hard stops to discover its range.
        The hand must be unobstructed. Progress is reported on the status channel.

        Args:
            finger_mask: Bitwise OR of CalibrationMask values.
                        CalibrationMask.ABORT (0) aborts a running calibration.

        Example:
            client.send_auto_calibration()  # all fingers
            client.send_auto_calibration(
                CalibrationMask.THUMB | CalibrationMask.INDEX
            )
            client.send_auto_calibration(CalibrationMask.ABORT)
        """
        if not 0 <= finger_mask <= 0b11111:
            raise InvalidArgumentError(
                "finger_mask must be a 5-bit CalibrationMask value (0..=0b11111)"
            )

        result = _lib.prohand_send_auto_calibration(self._handle, c_uint8(finger_mask))
        _check_result(result, "send_auto_calibration")

    def send_homing(self, enabled: bool = True):
        """
        Start or abort the homing sequence

        Args:
            enabled: True starts homing, False aborts it
        """
        result = _lib.prohand_send_homing(self._handle, int(enabled))
        _check_result(result, "send_homing")

    # ========================================================================
    # STATUS POLLING
    # ========================================================================

    def try_recv_message(self):
        """
        Try to receive the next status message (non-blocking).

        Returns a typed frame for the message's kind, or None when nothing is
        queued. Every message the firmware publishes reaches you here — actuator
        feedback and targets, joint-space targets in radians, IMU, power,
        warnings, state transitions and handedness — so there are no fields
        belonging to a different kind to misread.

        Shares one queue with try_recv_status(): each message goes to whichever is
        called first, so use one or the other per client.

        Returns:
            RotaryStatusFrame | RotaryTargetFrame | LinearStatusFrame |
            LinearTargetFrame | JointFrame | ImuFrame | PowerFrame | AlertFrame |
            StateFrame | HandednessFrame | OtherFrame | None

        Example:
            while (frame := client.try_recv_message()) is not None:
                if isinstance(frame, RotaryStatusFrame):
                    print(frame.positions)      # raw encoder counts
                elif isinstance(frame, RotaryTargetFrame):
                    print(frame.positions)      # commanded counts
                elif isinstance(frame, AlertFrame):
                    print(frame.severity, frame.code)
        """
        message = ProHandMessageC()
        result = _lib.prohand_try_recv_message(self._handle, byref(message))
        if result > 0:
            return _decode_message(message)
        if result == 0:
            return None
        _check_result(result, "try_recv_message")
        return None

    def try_recv_status(self) -> Optional[HandStatus]:
        """
        Try to receive status (non-blocking) — rotary/linear positions and targets only.

        Superseded by try_recv_message(), which covers every message kind. Kept for
        existing callers.

        One kind per call: `status_type` says which array was filled and the others
        are zero. Reading `rotary_targets` off a `status_type == 1` frame yields
        zeroes — that is this struct's shape, not a missing target echo.

        Returns:
            HandStatus if available, None otherwise
        """
        status_info = ProHandStatusInfo()
        result = _lib.prohand_try_recv_status(self._handle, pointer(status_info))

        if result > 0:
            return HandStatus(
                is_valid=bool(status_info.is_valid),
                status_type=int(status_info.status_type),
                rotary_positions=list(status_info.rotary_positions),
                linear_positions=list(status_info.linear_positions),
                rotary_targets=list(status_info.rotary_targets),
                linear_targets=list(status_info.linear_targets),
            )
        elif result == 0:
            return None
        else:
            # _check_result raises an exception on error, so this line is unreachable
            _check_result(result, "try_recv_status")
            return None  # Satisfy linter (never reached)


# ============================================================================
# MODULE-LEVEL FUNCTIONS
# ============================================================================


def discover_usb_devices(max_devices: int = 10) -> List[UsbDevice]:
    """
    Discover connected ProHand USB devices

    Args:
        max_devices: Maximum number of devices to return

    Returns:
        List of UsbDevice objects
    """
    devices_array = (ProHandUsbDeviceInfo * max_devices)()
    count = _lib.prohand_discover_usb_devices(devices_array, max_devices)

    if count < 0:
        _check_result(count, "discover_usb_devices")

    result = []
    for i in range(count):
        dev = devices_array[i]
        result.append(
            UsbDevice(
                port_name=string_at(dev.port_name).decode("utf-8")
                if dev.port_name
                else "",
                display_name=string_at(dev.display_name).decode("utf-8")
                if dev.display_name
                else "",
            )
        )

        # Free the strings allocated by C
        if dev.port_name:
            _lib.prohand_free_string(dev.port_name)
        if dev.display_name:
            _lib.prohand_free_string(dev.display_name)

    return result


def get_version() -> str:
    """Get SDK version"""
    version_ptr = _lib.prohand_get_version()
    return version_ptr.decode("utf-8") if version_ptr else "unknown"


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def _example():
    """Example usage of the SDK"""
    print(f"ProHand SDK Version: {get_version()}")

    # Discover USB devices
    devices = discover_usb_devices()
    print(f"\nFound {len(devices)} USB device(s):")
    for dev in devices:
        print(f"  - Display: {dev.display_name}, Port: {dev.port_name}")

    # Create client
    with ProHandClient(
        "tcp://127.0.0.1:5562",  # Command endpoint
        "tcp://127.0.0.1:5561",  # Status endpoint
        "tcp://127.0.0.1:5563",  # Hand streaming endpoint
        "tcp://127.0.0.1:5564",  # Wrist streaming endpoint
    ) as client:
        print(f"\nConnected: {client.is_connected()}")

        # Send ping
        client.send_ping()
        print("Sent ping")

        # Open hand (all fingers extended)
        positions = [0.0] * 20  # 20 joints: 5 fingers × 4 joints each
        client.send_hand_command(positions, torque=0.45)
        print("Opening hand...")

        # Poll status
        status = client.try_recv_status()
        if status and status.is_valid:
            print("\nStatus:")
            print(f"  Valid: {status.is_valid}")
            print(f"  Type: {status.status_type}")
            if status.status_type == 1:
                print(f"  Rotary positions: {status.rotary_positions[:4]}...")
            elif status.status_type == 2:
                print(f"  Linear positions: {status.linear_positions}...")


if __name__ == "__main__":
    _example()
