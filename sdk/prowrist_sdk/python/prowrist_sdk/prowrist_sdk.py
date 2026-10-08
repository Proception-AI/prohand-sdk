"""
ProWristCam Client SDK - Python Bindings

This module provides Python bindings for the WristCam Client SDK using ctypes.

Usage:
    from prowrist_sdk import WristCamClient

    # Connect to the left wrist camera via IPC (local)
    client = WristCamClient("ipc:///tmp/prowristcam-left-stream.ipc")

    # Or via TCP (remote / multi-host)
    client = WristCamClient("tcp://127.0.0.1:5565")

    # Poll for JPEG frames
    frame = client.try_recv_frame()
    if frame:
        print(f"Frame uid={frame.uid} ts={frame.timestamp} size={len(frame.jpeg)} bytes")
        with open("frame.jpg", "wb") as f:
            f.write(frame.jpeg)

    # Clean up
    client.close()

Wire format reference:
    Ping:  [0x02]
    Frame: [0x01][uid:2LE][ts:2LE][jpeg_len:4LE][jpeg_len bytes JPEG]

Requirements:
    - Place the compiled library (libprowristcam_client_sdk.so/.dylib/.dll) in:
      - ../../lib/ relative to this file (sdk/prowrist_sdk/lib/)
      - System library path
      - Or set PROWRISTCAM_SDK_LIB environment variable
"""

import ctypes
import os
import sys
from ctypes import (
    POINTER,
    c_char_p,
    c_int,
    c_uint8,
    c_uint32,
    c_uint64,
    Structure,
    pointer,
)
from typing import Optional
from dataclasses import dataclass
from enum import IntEnum


# ============================================================================
# LIBRARY LOADING
# ============================================================================


def _find_library():
    """Find the ProWristCam SDK library."""
    env_path = os.environ.get("PROWRISTCAM_SDK_LIB")
    if env_path and os.path.exists(env_path):
        return env_path

    import platform

    machine = platform.machine()

    if sys.platform == "darwin":
        lib_name = "libprowristcam_client_sdk.dylib"
    elif sys.platform == "win32":
        lib_name = "prowristcam_client_sdk.dll"
    elif sys.platform.startswith("linux"):
        if machine == "aarch64":
            lib_name = "libprowristcam_client_sdk_aarch64.so"
        elif machine in ("x86_64", "amd64", "i686", "i386"):
            lib_name = "libprowristcam_client_sdk.so"
        else:
            raise RuntimeError(
                f"Unsupported Linux architecture: {machine}. Supported: x86_64, aarch64"
            )
    else:
        raise RuntimeError(
            f"Unsupported platform: {sys.platform}. Supported: darwin, win32, linux"
        )

    script_dir = os.path.dirname(os.path.abspath(__file__))

    lib_path = os.path.join(script_dir, "..", "..", "lib", lib_name)
    if os.path.exists(lib_path):
        return lib_path

    return lib_name


_lib_path = _find_library()
_lib = ctypes.CDLL(_lib_path)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================


class WristCamResult(IntEnum):
    """Result codes returned by SDK functions."""

    SUCCESS = 0
    ERROR_NULL = -1
    ERROR_CONNECTION = -2
    ERROR_INVALID_ARGUMENT = -3
    ERROR_OTHER = -99


# ============================================================================
# CTYPES STRUCTURES
# ============================================================================


class WristCamClientHandle(Structure):
    """Opaque handle to WristCam client (do not instantiate directly)."""

    pass


class WristCamFrameInfo(Structure):
    """Raw JPEG frame from the wrist camera (mirrors the C struct)."""

    _fields_ = [
        ("is_valid", c_int),
        ("uid", c_uint32),
        ("timestamp", c_uint64),
        ("width", c_uint32),
        ("height", c_uint32),
        ("jpeg_data", POINTER(c_uint8)),
        ("jpeg_len", c_uint32),
    ]


@dataclass
class JpegFrame:
    """Python-friendly JPEG frame."""

    uid: int
    timestamp: int
    width: int
    height: int
    jpeg: bytes


# ============================================================================
# FUNCTION SIGNATURES
# ============================================================================

_lib.prowristcam_client_create.argtypes = [c_char_p]
_lib.prowristcam_client_create.restype = POINTER(WristCamClientHandle)

_lib.prowristcam_client_destroy.argtypes = [POINTER(WristCamClientHandle)]
_lib.prowristcam_client_destroy.restype = None

_lib.prowristcam_client_is_connected.argtypes = [POINTER(WristCamClientHandle)]
_lib.prowristcam_client_is_connected.restype = c_int

_lib.prowristcam_try_recv_frame.argtypes = [
    POINTER(WristCamClientHandle),
    POINTER(WristCamFrameInfo),
]
_lib.prowristcam_try_recv_frame.restype = c_int

_lib.prowristcam_free_frame.argtypes = [POINTER(WristCamFrameInfo)]
_lib.prowristcam_free_frame.restype = None

_lib.prowristcam_get_version.argtypes = []
_lib.prowristcam_get_version.restype = c_char_p


# ============================================================================
# EXCEPTIONS
# ============================================================================


class WristCamError(Exception):
    """Base exception for WristCam SDK errors."""

    pass


class ConnectionError(WristCamError):
    """Connection-related errors."""

    pass


class InvalidArgumentError(WristCamError):
    """Invalid argument errors."""

    pass


def _check_result(result: int, operation: str = "operation"):
    """Check result code and raise appropriate exception if error."""
    if result == WristCamResult.SUCCESS:
        return
    elif result == WristCamResult.ERROR_NULL:
        raise WristCamError(f"{operation}: Null pointer error")
    elif result == WristCamResult.ERROR_CONNECTION:
        raise ConnectionError(f"{operation}: Connection error")
    elif result == WristCamResult.ERROR_INVALID_ARGUMENT:
        raise InvalidArgumentError(f"{operation}: Invalid argument")
    else:
        raise WristCamError(f"{operation}: Unknown error ({result})")


# ============================================================================
# HIGH-LEVEL PYTHON API
# ============================================================================


class WristCamClient:
    """
    WristCam Client SDK - Python Interface.

    Subscribes to a ``prowristcam-headless-ipc-host`` ZMQ PUB endpoint and
    delivers JPEG frames.

    Args:
        stream_endpoint: ZeroMQ endpoint to subscribe to.
            IPC example: ``"ipc:///tmp/prowristcam-left-stream.ipc"``
            TCP example: ``"tcp://127.0.0.1:5565"``

    Raises:
        ConnectionError: If the client cannot be created.
    """

    def __init__(self, stream_endpoint: str):
        endpoint_bytes = stream_endpoint.encode("utf-8")
        self._handle = _lib.prowristcam_client_create(endpoint_bytes)

        if not self._handle:
            raise ConnectionError(
                f"Failed to create WristCam client for endpoint: {stream_endpoint}"
            )
        self._closed = False

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the client and free resources."""
        if not self._closed and self._handle:
            _lib.prowristcam_client_destroy(self._handle)
            self._handle = None
            self._closed = True

    def is_connected(self) -> bool:
        """Return True if connected to the stream publisher."""
        if self._closed:
            return False
        return bool(_lib.prowristcam_client_is_connected(self._handle))

    # ========================================================================
    # FRAME RECEPTION
    # ========================================================================

    def try_recv_frame(self) -> Optional[JpegFrame]:
        """
        Try to receive the next JPEG frame (non-blocking).

        Heartbeat / ping messages are skipped automatically.

        Returns:
            :class:`JpegFrame` if a frame is available, ``None`` otherwise.

        Raises:
            WristCamError: On SDK error.
        """
        if self._closed:
            raise WristCamError("Client is closed")

        c_frame = WristCamFrameInfo()
        result = _lib.prowristcam_try_recv_frame(self._handle, pointer(c_frame))

        if result > 0:
            jpeg = bytes()
            if c_frame.jpeg_data and c_frame.jpeg_len > 0:
                jpeg = ctypes.string_at(c_frame.jpeg_data, c_frame.jpeg_len)
            _lib.prowristcam_free_frame(pointer(c_frame))
            return JpegFrame(
                uid=c_frame.uid,
                timestamp=c_frame.timestamp,
                width=c_frame.width,
                height=c_frame.height,
                jpeg=jpeg,
            )
        elif result == 0:
            return None
        else:
            _check_result(result, "try_recv_frame")
            return None  # unreachable


# ============================================================================
# MODULE-LEVEL FUNCTIONS
# ============================================================================


def get_version() -> str:
    """Return the SDK version string."""
    ver = _lib.prowristcam_get_version()
    return ver.decode("utf-8") if ver else "unknown"


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def _example():
    """Quick smoke-test / example."""
    print(f"ProWristCam SDK Version: {get_version()}")

    endpoint = "ipc:///tmp/prowristcam-left-stream.ipc"
    print(f"\nConnecting to: {endpoint}")

    with WristCamClient(endpoint) as client:
        print(f"Connected: {client.is_connected()}")

        import time

        print("Polling for frames for 3 seconds...")
        frames_received = 0
        start = time.time()
        first_shown = False

        while (time.time() - start) < 3.0:
            frame = client.try_recv_frame()
            if frame:
                frames_received += 1
                if not first_shown:
                    first_shown = True
                    print("\nFirst frame received:")
                    print(f"  uid:       {frame.uid}")
                    print(f"  timestamp: {frame.timestamp}")
                    print(f"  jpeg size: {len(frame.jpeg)} bytes")
            time.sleep(0.001)

        elapsed = time.time() - start
        fps = frames_received / elapsed if elapsed > 0 else 0
        print(f"\nReceived {frames_received} frames in {elapsed:.2f}s ({fps:.1f} fps)")

        if frames_received == 0:
            print("\nNo frames received. Make sure:")
            print("  1. prowristcam-headless-ipc-host is running")
            print("  2. A USB camera is connected")
            print("  3. The endpoint matches the host configuration")


if __name__ == "__main__":
    _example()
