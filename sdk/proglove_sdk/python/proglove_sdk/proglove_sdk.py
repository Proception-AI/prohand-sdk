"""
ProGlove Client SDK - Python Bindings

This module provides Python bindings for the ProGlove Client SDK using ctypes.

Usage:
    from proglove_sdk import ProGloveClient

    # Create client (TCP - recommended for remote connections)
    # Default TCP ports (configs/devices.yaml: left_glove_status / right_glove_status): Left=5566, Right=5576
    client = ProGloveClient("tcp://127.0.0.1:5566")

    # Or use IPC for local connections
    client = ProGloveClient("ipc:///tmp/proglove-left-status.ipc")

    # Check connection by waiting for data
    client.send_ping()

    # Poll tactile status
    status = client.try_recv_status()
    if status and status.is_valid:
        print(f"Thumb DIP[0]: {status.t_dip[0]}")
        print(f"Index MCP[0]: {status.i_mcp[0]}")

    # Clean up
    client.close()

Taxel data is organized by joint segment (DIP/MCP/PIP per finger):
    - Thumb: DIP(6) + MCP(10) + PIP(4) = 20 taxels
    - Index/Middle/Ring/Pinky: DIP(4) + MCP(2) + PIP(2) = 8 taxels each
    - Palm: upper(16) + middle(16) + lower(16) = 48 taxels
    - Total: 100 taxels per hand

Requirements:
    - Place the compiled library (libproglove_client_sdk.so/.dylib/.dll) in:
      - ../../lib/ relative to this script (sdk/proglove_sdk/lib/)
      - System library path
      - Or set PROGLOVE_SDK_LIB environment variable
"""

import ctypes
import os
import sys
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_char_p,
    c_int,
    c_size_t,
    c_uint,
    c_uint8,
    c_void_p,
    Structure,
    pointer,
    c_uint16,
    c_float,
)
from typing import Callable, List, Optional
from dataclasses import dataclass
from enum import IntEnum


# ============================================================================
# LIBRARY LOADING
# ============================================================================


def _find_library():
    """Find the ProGlove SDK library"""
    # Check environment variable first
    env_path = os.environ.get("PROGLOVE_SDK_LIB")
    if env_path and os.path.exists(env_path):
        return env_path

    # Determine library name based on platform and architecture
    import platform

    machine = platform.machine()

    if sys.platform == "darwin":
        lib_name = "libproglove_client_sdk.dylib"
    elif sys.platform == "win32":
        lib_name = "proglove_client_sdk.dll"
    elif sys.platform.startswith("linux"):
        # On aarch64 (Jetson Nano), use the _aarch64 variant
        if machine == "aarch64":
            lib_name = "libproglove_client_sdk_aarch64.so"
        elif machine in ("x86_64", "amd64", "i686", "i386"):
            lib_name = "libproglove_client_sdk.so"
        else:
            raise RuntimeError(
                f"Unsupported Linux architecture: {machine}. Supported: x86_64, aarch64"
            )
    else:
        raise RuntimeError(
            f"Unsupported platform: {sys.platform}. Supported: darwin, win32, linux"
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
            f"Could not find ProGlove SDK library. "
            f"Expected '{lib_name}' in:\n"
            f"  - {os.path.join(script_dir, '..', '..', 'lib')}\n"
            f"  - System library path\n"
            f"  - Or set PROGLOVE_SDK_LIB environment variable"
        )


# Load the library
_lib_path = _find_library()
_lib = ctypes.CDLL(_lib_path)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class ProGloveResult(IntEnum):
    """Result codes returned by SDK functions"""

    SUCCESS = 0
    ERROR_NULL = -1
    ERROR_CONNECTION = -2
    ERROR_INVALID_ARGUMENT = -3
    ERROR_NOT_CONNECTED = -4
    ERROR_UNSUPPORTED = -5
    ERROR_OTHER = -99


# Taxel segment sizes (from taxel_mapping_v0.yaml)
# Thumb segments (larger than other fingers)
TAXELS_T_DIP = 6
TAXELS_T_MCP = 10
TAXELS_T_PIP = 4
# Index finger segments
TAXELS_I_DIP = 4
TAXELS_I_MCP = 2
TAXELS_I_PIP = 2
# Middle finger segments
TAXELS_M_DIP = 4
TAXELS_M_MCP = 2
TAXELS_M_PIP = 2
# Ring finger segments
TAXELS_R_DIP = 4
TAXELS_R_MCP = 2
TAXELS_R_PIP = 2
# Pinky finger segments
TAXELS_P_DIP = 4
TAXELS_P_MCP = 2
TAXELS_P_PIP = 2
# Palm segments
TAXELS_UPPER_PALM = 16
TAXELS_MIDDLE_PALM = 16
TAXELS_LOWER_PALM = 16


# ============================================================================
# STRUCTURES
# ============================================================================


class ProGloveClientHandle(Structure):
    """Opaque handle to ProGlove client (do not instantiate directly)"""

    pass


class ProGloveUsbDeviceInfo(Structure):
    """USB device information"""

    _fields_ = [
        ("port_name", POINTER(ctypes.c_char)),
        ("display_name", POINTER(ctypes.c_char)),
    ]


class ProGloveTactileStatus(Structure):
    """Tactile status from glove sensors (segment-based, u16 taxels, 12-bit ADC)"""

    _fields_ = [
        ("is_valid", c_int),
        ("timestamp", c_uint),
        ("uid", c_uint),
        # Thumb segments (6+10+4 = 20 taxels)
        ("t_dip", c_uint16 * TAXELS_T_DIP),
        ("t_mcp", c_uint16 * TAXELS_T_MCP),
        ("t_pip", c_uint16 * TAXELS_T_PIP),
        # Index segments (4+2+2 = 8 taxels)
        ("i_dip", c_uint16 * TAXELS_I_DIP),
        ("i_mcp", c_uint16 * TAXELS_I_MCP),
        ("i_pip", c_uint16 * TAXELS_I_PIP),
        # Middle segments (4+2+2 = 8 taxels)
        ("m_dip", c_uint16 * TAXELS_M_DIP),
        ("m_mcp", c_uint16 * TAXELS_M_MCP),
        ("m_pip", c_uint16 * TAXELS_M_PIP),
        # Ring segments (4+2+2 = 8 taxels)
        ("r_dip", c_uint16 * TAXELS_R_DIP),
        ("r_mcp", c_uint16 * TAXELS_R_MCP),
        ("r_pip", c_uint16 * TAXELS_R_PIP),
        # Pinky segments (4+2+2 = 8 taxels)
        ("p_dip", c_uint16 * TAXELS_P_DIP),
        ("p_mcp", c_uint16 * TAXELS_P_MCP),
        ("p_pip", c_uint16 * TAXELS_P_PIP),
        # Palm segments (16+16+16 = 48 taxels)
        ("upper_palm", c_uint16 * TAXELS_UPPER_PALM),
        ("middle_palm", c_uint16 * TAXELS_MIDDLE_PALM),
        ("lower_palm", c_uint16 * TAXELS_LOWER_PALM),
    ]


class ProGloveImuStatus(Structure):
    """IMU status — fused orientation quaternion from the on-board IMU"""

    _fields_ = [
        ("is_valid", c_int),
        ("timestamp", c_uint),
        ("qw", c_float),
        ("qx", c_float),
        ("qy", c_float),
        ("qz", c_float),
    ]


class ProGloveFilterConfig(Structure):
    """Tunable tactile filter parameters — deadzone sensitivity, stuck-pixel
    spatial-isolation threshold, and stuck-detection timing. Fetch sensible
    starting values with get_default_filter_config(), tweak only the fields
    you care about, then apply with ProGloveClient.set_filter_config() — the
    underlying command replaces the whole config, not a per-field patch."""

    _fields_ = [
        ("deadzone_on", c_float),  # fraction of ADC max above which a taxel activates
        ("deadzone_off", c_float),  # fraction below which an active taxel turns off
        ("denoise_enabled", c_int),  # stuck-pixel masking on/off
        (
            "stuck_spatial_threshold",
            c_uint16,
        ),  # raw ADC counts vs. segment neighbors' median
        (
            "stuck_streak_on_frames",
            c_uint,
        ),  # consecutive flat+isolated frames before flagging, at ~100 Hz
    ]


@dataclass
class UsbDevice:
    """Python-friendly USB device info"""

    port_name: str
    display_name: str


@dataclass
class TactileStatus:
    """
    Python-friendly tactile status from glove sensors (segment-based)

    Tactile data is organized by joint segment (DIP/MCP/PIP) for each finger.
    Values are 0-4095 (12-bit ADC) where higher values indicate more pressure.
    """

    is_valid: bool
    timestamp: int
    uid: int
    # Thumb segments
    t_dip: List[int]
    t_mcp: List[int]
    t_pip: List[int]
    # Index segments
    i_dip: List[int]
    i_mcp: List[int]
    i_pip: List[int]
    # Middle segments
    m_dip: List[int]
    m_mcp: List[int]
    m_pip: List[int]
    # Ring segments
    r_dip: List[int]
    r_mcp: List[int]
    r_pip: List[int]
    # Pinky segments
    p_dip: List[int]
    p_mcp: List[int]
    p_pip: List[int]
    # Palm segments
    upper_palm: List[int]
    middle_palm: List[int]
    lower_palm: List[int]


def _tactile_from_c(c_status: "ProGloveTactileStatus") -> TactileStatus:
    """Convert a C `ProGloveTactileStatus` into the Python `TactileStatus`."""
    return TactileStatus(
        is_valid=bool(c_status.is_valid),
        timestamp=c_status.timestamp,
        uid=c_status.uid,
        t_dip=list(c_status.t_dip),
        t_mcp=list(c_status.t_mcp),
        t_pip=list(c_status.t_pip),
        i_dip=list(c_status.i_dip),
        i_mcp=list(c_status.i_mcp),
        i_pip=list(c_status.i_pip),
        m_dip=list(c_status.m_dip),
        m_mcp=list(c_status.m_mcp),
        m_pip=list(c_status.m_pip),
        r_dip=list(c_status.r_dip),
        r_mcp=list(c_status.r_mcp),
        r_pip=list(c_status.r_pip),
        p_dip=list(c_status.p_dip),
        p_mcp=list(c_status.p_mcp),
        p_pip=list(c_status.p_pip),
        upper_palm=list(c_status.upper_palm),
        middle_palm=list(c_status.middle_palm),
        lower_palm=list(c_status.lower_palm),
    )


@dataclass
class ImuStatus:
    """Python-friendly IMU status — fused orientation quaternion."""

    is_valid: bool
    timestamp: int
    qw: float
    qx: float
    qy: float
    qz: float


# C callback type for proglove_perform_ota's progress_cb parameter:
# void(*)(unsigned int pages_sent, unsigned int total_pages, void *user_data)
OtaProgressCFunc = CFUNCTYPE(None, c_uint, c_uint, c_void_p)

# ============================================================================
# FUNCTION SIGNATURES
# ============================================================================

# Client lifecycle
_lib.proglove_client_create.argtypes = [c_char_p]
_lib.proglove_client_create.restype = POINTER(ProGloveClientHandle)

_lib.proglove_client_destroy.argtypes = [POINTER(ProGloveClientHandle)]
_lib.proglove_client_destroy.restype = None

_lib.proglove_client_is_connected.argtypes = [POINTER(ProGloveClientHandle)]
_lib.proglove_client_is_connected.restype = c_int

# Ping (verifies connection by waiting for data)
_lib.proglove_send_ping.argtypes = [POINTER(ProGloveClientHandle)]
_lib.proglove_send_ping.restype = c_int

# OTA
_lib.proglove_perform_ota.argtypes = [
    POINTER(ProGloveClientHandle),
    POINTER(c_uint8),
    c_size_t,
    POINTER(c_uint8),
    POINTER(c_uint8),
    c_uint,
    OtaProgressCFunc,
    c_void_p,
]
_lib.proglove_perform_ota.restype = c_int

# Calibration
_lib.proglove_calibrate_and_wait.argtypes = [POINTER(ProGloveClientHandle), c_uint]
_lib.proglove_calibrate_and_wait.restype = c_int

# Tactile filter control
_lib.proglove_set_denoise_enabled.argtypes = [POINTER(ProGloveClientHandle), c_int]
_lib.proglove_set_denoise_enabled.restype = c_int

_lib.proglove_get_default_filter_config.argtypes = [POINTER(ProGloveFilterConfig)]
_lib.proglove_get_default_filter_config.restype = c_int

_lib.proglove_set_filter_config.argtypes = [
    POINTER(ProGloveClientHandle),
    POINTER(ProGloveFilterConfig),
]
_lib.proglove_set_filter_config.restype = c_int

# Status polling
_lib.proglove_try_recv_status.argtypes = [
    POINTER(ProGloveClientHandle),
    POINTER(ProGloveTactileStatus),
]
_lib.proglove_try_recv_status.restype = c_int

_lib.proglove_try_recv_raw_tactile.argtypes = [
    POINTER(ProGloveClientHandle),
    POINTER(ProGloveTactileStatus),
]
_lib.proglove_try_recv_raw_tactile.restype = c_int

_lib.proglove_has_raw_tactile.argtypes = [POINTER(ProGloveClientHandle)]
_lib.proglove_has_raw_tactile.restype = c_int

_lib.proglove_try_recv_imu_status.argtypes = [
    POINTER(ProGloveClientHandle),
    POINTER(ProGloveImuStatus),
]
_lib.proglove_try_recv_imu_status.restype = c_int

# USB discovery
_lib.proglove_discover_usb_devices.argtypes = [POINTER(ProGloveUsbDeviceInfo), c_int]
_lib.proglove_discover_usb_devices.restype = c_int

# proglove_free_string expects *mut c_char (mutable pointer)
_lib.proglove_free_string.argtypes = [POINTER(ctypes.c_char)]
_lib.proglove_free_string.restype = None

# Version
_lib.proglove_get_version.argtypes = []
_lib.proglove_get_version.restype = c_char_p


# ============================================================================
# EXCEPTIONS
# ============================================================================


class ProGloveError(Exception):
    """Base exception for ProGlove SDK errors"""

    pass


class ConnectionError(ProGloveError):
    """Connection-related errors"""

    pass


class InvalidArgumentError(ProGloveError):
    """Invalid argument errors"""

    pass


def _check_result(result: int, operation: str = "operation"):
    """Check result code and raise exception if error"""
    if result == ProGloveResult.SUCCESS:
        return
    elif result == ProGloveResult.ERROR_NULL:
        raise ProGloveError(f"{operation}: Null pointer error")
    elif result == ProGloveResult.ERROR_CONNECTION:
        raise ConnectionError(f"{operation}: Connection error")
    elif result == ProGloveResult.ERROR_INVALID_ARGUMENT:
        raise InvalidArgumentError(f"{operation}: Invalid argument")
    elif result == ProGloveResult.ERROR_NOT_CONNECTED:
        raise ConnectionError(f"{operation}: Not connected")
    elif result == ProGloveResult.ERROR_UNSUPPORTED:
        raise ProGloveError(f"{operation}: Unsupported operation")
    else:
        raise ProGloveError(f"{operation}: Unknown error ({result})")


# ============================================================================
# HIGH-LEVEL PYTHON API
# ============================================================================


class ProGloveClient:
    """
    ProGlove Client SDK - Python Interface

    This class provides a high-level Python interface to receive tactile
    sensor data from ProGlove devices via ZeroMQ PUB/SUB.

    Args:
        status_endpoint: ZeroMQ endpoint for status
            TCP example: "tcp://127.0.0.1:5566"
            IPC example: "ipc:///tmp/proglove-left-status.ipc"

    Raises:
        ConnectionError: If connection fails
    """

    def __init__(self, status_endpoint: str):
        """
        Create a new ProGlove client

        Args:
            status_endpoint: ZeroMQ endpoint for status (e.g., "tcp://127.0.0.1:5566")

        Raises:
            ConnectionError: If connection fails
        """
        endpoint_bytes = status_endpoint.encode("utf-8")
        self._handle = _lib.proglove_client_create(endpoint_bytes)

        if not self._handle:
            raise ConnectionError(
                f"Failed to create ProGlove client for endpoint: {status_endpoint}"
            )

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
            _lib.proglove_client_destroy(self._handle)
            self._handle = None
            self._closed = True

    def is_connected(self) -> bool:
        """Check if connected to device"""
        if self._closed:
            return False
        return bool(_lib.proglove_client_is_connected(self._handle))

    # ========================================================================
    # COMMAND METHODS
    # ========================================================================

    def send_ping(self):
        """
        Send ping - verify connection by waiting for data

        Since ProGlove uses PUB/SUB (not REQ/REP like ProHand), this method
        waits for tactile data to be received, confirming the connection is working.

        Raises:
            ConnectionError: On connection error or timeout
        """
        if self._closed:
            raise ConnectionError("Client is closed")
        result = _lib.proglove_send_ping(self._handle)
        # 0 means success (PROGLOVE_SUCCESS), negative means error
        if result < 0:
            _check_result(result, "send_ping")

    def perform_ota(
        self,
        image: bytes,
        key: bytes,
        sig: bytes,
        on_progress: Optional[Callable[[int, int], None]] = None,
        timeout: float = 15.0,
    ) -> bool:
        """
        Full OTA update: sends the image + key/sig, then answers every
        firmware page request automatically, calling on_progress(pages_sent,
        total_pages) after each page (if given). Blocks until the transfer
        succeeds, fails, or stalls for `timeout` seconds with no reply (the
        timeout resets on every reply, so it's a stall detector, not a cap
        on total transfer time).

        Args:
            image: Firmware image bytes.
            key: 32-byte ed25519 public key (currently unenforced firmware-side).
            sig: 64-byte ed25519 signature (currently unenforced firmware-side).
            on_progress: Optional callback invoked after each page is sent.
            timeout: Seconds to wait for each firmware reply before giving up (default: 15.0).

        Returns:
            True on success, False on firmware-reported error or timeout.

        Raises:
            InvalidArgumentError: If key/sig are not exactly 32/64 bytes.
            ConnectionError: On send failure.
        """
        if self._closed:
            raise ConnectionError("Client is closed")
        if len(key) != 32:
            raise InvalidArgumentError(f"key must be 32 bytes, got {len(key)}")
        if len(sig) != 64:
            raise InvalidArgumentError(f"sig must be 64 bytes, got {len(sig)}")

        image_buf = (c_uint8 * len(image)).from_buffer_copy(image)
        key_buf = (c_uint8 * 32).from_buffer_copy(key)
        sig_buf = (c_uint8 * 64).from_buffer_copy(sig)

        if on_progress is not None:
            c_callback = OtaProgressCFunc(
                lambda pages_sent, total_pages, _user_data: on_progress(
                    pages_sent, total_pages
                )
            )
        else:
            c_callback = OtaProgressCFunc()  # NULL function pointer

        result = _lib.proglove_perform_ota(
            self._handle,
            image_buf,
            len(image),
            key_buf,
            sig_buf,
            int(timeout * 1000),
            c_callback,
            None,
        )
        if result < 0:
            _check_result(result, "perform_ota")
        return result == 1

    def calibrate(self, timeout: float = 5.0) -> bool:
        """
        Full calibration cycle: clear the existing baseline, then start a
        fresh snapshot, blocking until BaselineCommitted arrives or the
        timeout elapses (requires streaming to be on — the driver needs
        ~100 live tactile frames to complete the snapshot).

        Args:
            timeout: Seconds to wait for BaselineCommitted (default: 5.0).

        Returns:
            True if calibration completed within the timeout, False if it
            timed out (baseline may still complete later).

        Raises:
            ConnectionError: On send failure.
        """
        if self._closed:
            raise ConnectionError("Client is closed")
        result = _lib.proglove_calibrate_and_wait(self._handle, int(timeout * 1000))
        if result < 0:
            _check_result(result, "calibrate")
        return result == 1

    def set_denoise_enabled(self, enabled: bool) -> None:
        """Toggle stuck-pixel masking."""
        if self._closed:
            raise ConnectionError("Client is closed")
        result = _lib.proglove_set_denoise_enabled(self._handle, 1 if enabled else 0)
        _check_result(result, "set_denoise_enabled")

    def set_filter_config(self, config: ProGloveFilterConfig) -> None:
        """
        Replace the entire tactile filter configuration — deadzone on/off,
        stuck-pixel spatial-isolation threshold, and stuck-detection timing.
        This replaces the whole config, not a per-field patch — start from
        get_default_filter_config() and override only what you need.
        """
        if self._closed:
            raise ConnectionError("Client is closed")
        result = _lib.proglove_set_filter_config(self._handle, byref(config))
        _check_result(result, "set_filter_config")

    # ========================================================================
    # STATUS POLLING
    # ========================================================================

    def try_recv_status(self) -> Optional[TactileStatus]:
        """
        Try to receive tactile status (non-blocking)

        Returns:
            TactileStatus if available, None otherwise
        """
        c_status = ProGloveTactileStatus()
        result = _lib.proglove_try_recv_status(self._handle, pointer(c_status))

        if result > 0:
            return _tactile_from_c(c_status)
        elif result == 0:
            return None
        else:
            _check_result(result, "try_recv_status")
            return None  # Satisfy linter (never reached)

    def try_recv_raw_tactile(self) -> Optional[TactileStatus]:
        """
        Try to receive a pre-filter RAW tactile frame (non-blocking).

        Pure hardware ADC from the driver's secondary raw node (no host
        filter/baseline). Poll alongside try_recv_status() to capture raw +
        processed together.

        Returns:
            TactileStatus if a raw frame is available, None otherwise (also
            None when the endpoint has no raw node — see has_raw_tactile()).
        """
        c_status = ProGloveTactileStatus()
        result = _lib.proglove_try_recv_raw_tactile(self._handle, pointer(c_status))

        if result > 0:
            return _tactile_from_c(c_status)
        elif result == 0:
            return None
        else:
            _check_result(result, "try_recv_raw_tactile")
            return None  # Satisfy linter (never reached)

    def has_raw_tactile(self) -> bool:
        """
        Whether this client derived a raw tactile endpoint (a local
        -status.ipc path). True does not guarantee the driver is publishing
        raw — only that the client is subscribed and will surface frames if so.
        """
        return _lib.proglove_has_raw_tactile(self._handle) > 0

    def try_recv_imu_status(self) -> Optional[ImuStatus]:
        """
        Try to receive IMU status (non-blocking)

        Returns:
            ImuStatus if the next message was IMU data, None otherwise
            (including when the next message was a different type — call
            this alongside try_recv_status() and check for None on each).
        """
        c_status = ProGloveImuStatus()
        result = _lib.proglove_try_recv_imu_status(self._handle, pointer(c_status))

        if result > 0:
            return ImuStatus(
                is_valid=bool(c_status.is_valid),
                timestamp=c_status.timestamp,
                qw=c_status.qw,
                qx=c_status.qx,
                qy=c_status.qy,
                qz=c_status.qz,
            )
        elif result == 0:
            return None
        else:
            _check_result(result, "try_recv_imu_status")
            return None  # Satisfy linter (never reached)


# ============================================================================
# MODULE-LEVEL FUNCTIONS
# ============================================================================


def discover_usb_devices(max_devices: int = 16) -> List[UsbDevice]:
    """
    Discover connected ProGlove USB devices

    Args:
        max_devices: Maximum number of devices to return

    Returns:
        List of UsbDevice objects
    """
    devices_array = (ProGloveUsbDeviceInfo * max_devices)()
    count = _lib.proglove_discover_usb_devices(devices_array, max_devices)

    if count < 0:
        _check_result(count, "discover_usb_devices")

    result = []
    for i in range(count):
        dev = devices_array[i]
        # Convert mutable char pointers to Python strings
        port = ""
        display = ""
        if dev.port_name:
            port = ctypes.string_at(dev.port_name).decode("utf-8")
        if dev.display_name:
            display = ctypes.string_at(dev.display_name).decode("utf-8")
        result.append(UsbDevice(port_name=port, display_name=display))

        # Free the strings allocated by Rust
        if dev.port_name:
            _lib.proglove_free_string(dev.port_name)
        if dev.display_name:
            _lib.proglove_free_string(dev.display_name)

    return result


def get_version() -> str:
    """Get SDK version"""
    version_ptr = _lib.proglove_get_version()
    return version_ptr.decode("utf-8") if version_ptr else "unknown"


def get_default_filter_config() -> ProGloveFilterConfig:
    """Default tactile filter configuration — a sensible starting point to
    tweak before calling ProGloveClient.set_filter_config()."""
    config = ProGloveFilterConfig()
    result = _lib.proglove_get_default_filter_config(byref(config))
    _check_result(result, "get_default_filter_config")
    return config


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def _example():
    """Example usage of the SDK"""
    print(f"ProGlove SDK Version: {get_version()}")

    # Discover USB devices
    devices = discover_usb_devices()
    print(f"\nFound {len(devices)} USB device(s):")
    for dev in devices:
        print(f"  - Display: {dev.display_name}, Port: {dev.port_name}")

    if not devices:
        print("\nNo devices found. Make sure a ProGlove is connected.")
        print("You can still try connecting if proglove-headless-ipc-host is running.")

    # Create client (connects to left glove via TCP)
    # Default TCP ports: Left=5566, Right=5576 (see configs/devices.yaml)
    endpoint = "tcp://127.0.0.1:5566"
    print(f"\nConnecting to: {endpoint}")

    with ProGloveClient(endpoint) as client:
        print(f"Connected: {client.is_connected()}")

        # Verify connection by waiting for data
        print("\nVerifying connection (waiting for data)...")
        try:
            client.send_ping()
            print("Connection verified!")
        except ConnectionError as e:
            print(f"Warning: {e}")

        # Poll status for 2 seconds
        import time

        print("Polling tactile status for 2 seconds...")
        samples_received = 0
        start_time = time.time()
        first_shown = False

        while (time.time() - start_time) < 2.0:
            status = client.try_recv_status()
            if status and status.is_valid:
                samples_received += 1
                if not first_shown:
                    first_shown = True
                    # Show first sample details
                    print("\nFirst sample received:")
                    print(f"  Timestamp: {status.timestamp}")
                    print(f"  UID: {status.uid}")
                    print(f"  Thumb DIP ({len(status.t_dip)} taxels): {status.t_dip}")
                    print(
                        f"  Thumb MCP ({len(status.t_mcp)} taxels): "
                        f"{status.t_mcp[:5]}..."
                    )
                    print(f"  Index DIP ({len(status.i_dip)} taxels): {status.i_dip}")
                    print(
                        f"  Upper Palm ({len(status.upper_palm)} taxels): "
                        f"{status.upper_palm[:5]}..."
                    )
            time.sleep(0.001)  # Small sleep to avoid busy-waiting

        elapsed = time.time() - start_time
        rate = samples_received / elapsed if elapsed > 0 else 0
        print(
            f"\nReceived {samples_received} samples in {elapsed:.2f}s ({rate:.1f} Hz)"
        )

        if samples_received == 0:
            print("\nNo data received. Make sure:")
            print("  1. proglove-headless-ipc-host is running")
            print("  2. ProGlove hardware is connected")
            print("  3. Endpoint matches the host configuration")


if __name__ == "__main__":
    _example()
