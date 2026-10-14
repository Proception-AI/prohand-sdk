"""GENERATED from prohand_sdk.h by gen_ffi_constants.py. Do not edit."""

from enum import IntEnum


class ProHandResult(IntEnum):
    """Result codes returned by SDK functions."""

    SUCCESS = 0
    ERROR_NULL = -1
    ERROR_CONNECTION = -2
    ERROR_INVALID_ARGUMENT = -3
    ERROR_NOT_CONNECTED = -4
    ERROR_UNSUPPORTED = -5
    ERROR_OTHER = -99


class CalibrationMask(IntEnum):
    """Finger bitmask values for send_auto_calibration(). OR them together."""

    ABORT = 0
    THUMB = 1
    INDEX = 2
    MIDDLE = 4
    RING = 8
    PINKY = 16
    ALL = 31


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
    HAND_OBSERVED_STATE = 20
    HAND_HEALTH = 21
    SYNC_STATUS = 22
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
    ASSISTED_TRIM = 111
    TRIM_VALIDATION = 112
    FAN_STATUS = 113
    FAN_CURVE_CONFIG = 114
    THUMB_CO_CONTRACTION = 115
    CPU_LOAD = 116
    TASK_LOAD = 117
    SECTION_LOAD = 118
    IMU_NOISE_CALIBRATION = 119
    LED_BRIGHTNESS = 120
    LED_OVERRIDE = 121
    STORE = 128
    MOTION = 129
