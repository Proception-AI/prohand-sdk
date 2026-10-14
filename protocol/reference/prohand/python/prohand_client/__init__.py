"""ProHand protocol reference client.

The wire contract, and nothing else: packed Cap'n Proto messages from the
public schema over ZeroMQ. Three roles, one class each:

- ``ServiceClient``: request/reply commands (ping, streaming mode, zero
  calibration, homing) on the driver's REQ/REP endpoint.
- ``Publisher``: streamed hand and wrist commands on the driver's two SUB
  endpoints, newest setpoint only.
- ``Subscriber``: the status stream, each frame with its envelope header and
  the host time the driver fills once the clocks are synchronised.

Every message builder is also exposed as a plain ``encode_*`` function that
returns the packed bytes, so a program can use its own transport, and so the
conformance tests can check the bytes without a socket.

Synchronous, one thread. ``python -m prohand_client`` runs the quickstart.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import capnp
import zmq

__all__ = [
    "DEFAULT_RECONNECT_AFTER_S",
    "DEFAULT_ROTARY_VELOCITY",
    "FINGERS",
    "SCHEMA_DIR",
    "Header",
    "Publisher",
    "ServiceClient",
    "Status",
    "Subscriber",
    "encode_hand_command",
    "encode_homing",
    "encode_linear_command",
    "encode_ping",
    "encode_rotary_command",
    "encode_streaming_mode",
    "encode_streaming_mode_continuous",
    "encode_wrist_command",
    "encode_zero_calibration",
    "parse_status_message",
    "prohand_capnp",
]

# The servo Running Speed register reads 0 as stop, so an unset velocity holds
# the hand still. 50 is the fleet default every other producer uses.
DEFAULT_ROTARY_VELOCITY = 50

# A SUB socket never learns that its publisher went away; after this much
# silence the subscriber reopens its socket, which also covers a driver that
# restarted on a re-created ipc file.
DEFAULT_RECONNECT_AFTER_S = 5.0

FINGERS = ("thumb", "index", "middle", "ring", "pinky")

SCHEMA_ENV = "PROHAND_SCHEMA_DIR"


def _schema_dir() -> Path:
    """The public schema: ``PROHAND_SCHEMA_DIR`` when set; inside the
    monorepo its public edition, so an in-tree build never reads a stale
    vendored copy; in the shipped package the copy vendored beside the
    reference clients."""
    if os.environ.get(SCHEMA_ENV):
        return Path(os.environ[SCHEMA_ENV])
    here = Path(__file__).resolve().parent
    candidates = []
    if len(here.parents) > 6:
        candidates.append(
            here.parents[6] / "schemas" / "capnp" / "schema" / "prohand" / "public"
        )
    if len(here.parents) > 3:
        candidates.append(here.parents[3] / "schema" / "prohand")
    for candidate in candidates:
        if (candidate / "prohand_sdk.capnp").is_file():
            return candidate
    raise FileNotFoundError(
        "prohand_sdk.capnp not found; set PROHAND_SCHEMA_DIR to the directory holding it"
    )


SCHEMA_DIR = _schema_dir()
prohand_capnp: Any = capnp.load(
    str(SCHEMA_DIR / "prohand_sdk.capnp"), imports=[str(SCHEMA_DIR)]
)


# ── Encoding ────────────────────────────────────────────────────────────────


def _packed(command: Any) -> bytes:
    return command.to_bytes_packed()


def _new_command() -> Any:
    return prohand_capnp.ProHandCommand.new_message()


def _round_half_away(value: float) -> int:
    """Round half away from zero, the one rule all three reference clients
    share; Python's ``round`` goes half to even."""
    return int(value + math.copysign(0.5, value))


def _i16(value: float) -> int:
    return max(-32768, min(32767, _round_half_away(value)))


def _scaled_position(radians: float) -> int:
    """Joint angle in centi-degrees, the ``CompactJointState.scaledPosition``
    unit, clamped to the i16 range and never wrapped."""
    return _i16(math.degrees(radians) * 100.0)


def _normalized(value: float) -> int:
    """[-1, 1] onto the full i16 range, the ``normalizedVelOrTau`` unit."""
    return _i16(max(-1.0, min(1.0, value)) * 32767.0)


def encode_ping() -> bytes:
    command = _new_command()
    command.ping = None
    return _packed(command)


def encode_streaming_mode(enabled: bool) -> bytes:
    """``True`` is on-demand streaming (one echo per accepted command),
    ``False`` is off. See ``encode_streaming_mode_continuous``."""
    command = _new_command()
    mode = command.init("handRequest").init("streamingMode")
    if enabled:
        mode.onDemand = None
    else:
        mode.off = None
    return _packed(command)


def encode_streaming_mode_continuous(space_filter: str = "jointSpace") -> bytes:
    """Continuous streaming: the firmware re-emits the cached joint targets
    every control tick and admits only commands inside ``space_filter``
    (``free``, ``jointSpace``, ``actuatorSpace`` or
    ``jointSpaceHandWithActuatorSpaceWrist``)."""
    command = _new_command()
    command.init("handRequest").init("streamingMode").continuous = space_filter
    return _packed(command)


def encode_zero_calibration(motor_id: int | None = None) -> bytes:
    """Zero calibration of one rotary servo, or of all sixteen."""
    command = _new_command()
    calib = command.init("handRequest").init("zeroCalib", 16)
    for i in range(16):
        calib[i] = motor_id is None or i == motor_id
    return _packed(command)


def encode_homing(start: bool = True) -> bytes:
    """Start or abort the firmware's homing sequence, which drives every
    joint to its neutral pose. Not zero calibration."""
    command = _new_command()
    command.init("handRequest").homing = start
    return _packed(command)


def encode_rotary_command(
    positions: Sequence[int],
    torques: Sequence[int],
    velocities: Sequence[int] | None = None,
) -> bytes:
    """Sixteen servo setpoints. ``velocities`` caps each servo's speed and
    must be non-zero to move; left out, every servo gets the fleet default."""
    if len(positions) != 16 or len(torques) != 16:
        raise ValueError("exactly 16 positions and 16 torques")
    if velocities is None:
        velocities = [DEFAULT_ROTARY_VELOCITY] * 16
    if len(velocities) != 16:
        raise ValueError("exactly 16 velocities")
    command = _new_command()
    servos = command.init("rotaryGrpCommand", 16)
    for i in range(16):
        servos[i].position = int(positions[i])
        servos[i].torque = int(torques[i])
        servos[i].velocity = int(velocities[i])
    return _packed(command)


def encode_linear_command(positions: Sequence[int], speeds: Sequence[int]) -> bytes:
    """Two wrist actuator setpoints."""
    if len(positions) != 2 or len(speeds) != 2:
        raise ValueError("exactly 2 positions and 2 speeds")
    command = _new_command()
    actuators = command.init("linearGrpCommand", 2)
    for i in range(2):
        actuators[i].position = int(positions[i])
        actuators[i].speed = int(speeds[i])
    return _packed(command)


_uid = 0


def _next_uid() -> int:
    global _uid
    _uid = (_uid + 1) & 0xFFFF
    return _uid


def _timestamp_ms() -> int:
    return int(time.monotonic() * 1000.0) & 0xFFFF


def encode_hand_command(
    pose: Mapping[str, Sequence[float]],
    degrees: bool = False,
    torque: float | Sequence[float] = 0.45,
    velocity_saturation: float = 1.0,
    uid: int | None = None,
    timestamp_ms: int | None = None,
) -> bytes:
    """Finger joint targets. ``pose`` maps each finger name in ``FINGERS`` to
    four joint angles (radians, or degrees with ``degrees=True``); a missing
    finger or joint reads as zero. ``torque`` is one normalised level for all
    fingers or one per finger. ``velocity_saturation`` is the global speed
    cap in [0, 1]; the wire default is 0, which does not move. ``uid`` and
    ``timestamp_ms`` are taken from a counter and the monotonic clock when
    not given."""
    if isinstance(torque, (int, float)):
        torques = [float(torque)] * 5
    else:
        torques = [float(t) for t in torque]
        if len(torques) != 5:
            raise ValueError("one torque per finger, five in all")
    command = _new_command()
    hand = command.init("handStateCommand")
    hand.timestamp = _timestamp_ms() if timestamp_ms is None else timestamp_ms & 0xFFFF
    hand.uid = _next_uid() if uid is None else uid & 0xFFFF
    hand.velocitySaturation = _round_half_away(
        max(0.0, min(1.0, velocity_saturation)) * 255.0
    )
    for finger, level in zip(FINGERS, torques):
        joints = hand.init(finger, 4)
        angles = pose.get(finger, ())
        for i in range(4):
            angle = float(angles[i]) if i < len(angles) else 0.0
            if degrees:
                angle = math.radians(angle)
            joints[i].scaledPosition = _scaled_position(angle)
            joints[i].normalizedVelOrTau = _normalized(level)
    return _packed(command)


def encode_wrist_command(
    positions: Sequence[float],
    velocity_norm: Sequence[float],
    degrees: bool = False,
    uid: int | None = None,
    timestamp_ms: int | None = None,
) -> bytes:
    """Two wrist joint targets with a normalised velocity each."""
    if len(positions) != 2 or len(velocity_norm) != 2:
        raise ValueError("exactly 2 positions and 2 velocities")
    command = _new_command()
    wrist = command.init("wristStateCommand")
    wrist.timestamp = _timestamp_ms() if timestamp_ms is None else timestamp_ms & 0xFFFF
    wrist.uid = _next_uid() if uid is None else uid & 0xFFFF
    joints = wrist.init("wrist", 2)
    for i in range(2):
        angle = float(positions[i])
        if degrees:
            angle = math.radians(angle)
        joints[i].scaledPosition = _scaled_position(angle)
        joints[i].normalizedVelOrTau = _normalized(float(velocity_norm[i]))
    return _packed(command)


# ── Decoding ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Header:
    """What every status frame carries beside its body: the device clock,
    the control tick the stamp was taken in (``None`` when unbound), the
    sequence counter, the boot count, frames dropped before this one and the
    clock-sync epoch."""

    t_device_us: int = 0
    tick: int | None = None
    seq: int = 0
    boot: int = 0
    dropped: int = 0
    sync: int = 0


@dataclass(frozen=True)
class Status:
    """One status frame. ``t_host_us`` is the device clock mapped onto the
    host's, filled by the driver once the clocks are synchronised. ``body``
    is the Cap'n Proto reader; ``which`` names the variant it carries."""

    header: Header
    t_host_us: int | None
    body: Any

    @property
    def which(self) -> str:
        return str(self.body.which())


def parse_status_message(data: bytes) -> Status:
    status = prohand_capnp.ProHandStatus.from_bytes_packed(data)
    header = Header()
    if status._has("header"):
        h = status.header
        stamp = h.stamp
        tick = stamp.frame.tick if stamp.frame.which() == "tick" else None
        header = Header(
            t_device_us=int(stamp.tDeviceUs),
            tick=tick,
            seq=int(h.seq),
            boot=int(h.boot),
            dropped=int(h.dropped),
            sync=int(h.sync),
        )
    t_host_us = int(status.tHostUs) or None
    return Status(header=header, t_host_us=t_host_us, body=status)


# ── Transport ───────────────────────────────────────────────────────────────


class ServiceClient:
    """Request/reply commands. A request the driver does not answer within
    the timeout returns ``False`` and reopens the socket, since a REQ socket
    that is waiting for a reply accepts no further request."""

    def __init__(
        self, command_endpoint: str, context: zmq.Context | None = None
    ) -> None:
        self._owns_context = context is None
        self._context = context or zmq.Context()
        self._endpoint = command_endpoint
        self._sock: zmq.Socket | None = None

    def connect(self) -> ServiceClient:
        self._open()
        return self

    def _open(self) -> zmq.Socket:
        if self._sock is not None:
            self._sock.close(linger=0)
        sock = self._context.socket(zmq.REQ)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(self._endpoint)
        self._sock = sock
        return sock

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close(linger=0)
            self._sock = None
        if self._owns_context:
            self._context.term()

    def request(self, payload: bytes, timeout_ms: int = 1000) -> bytes | None:
        """Send one command and wait for the reply; ``None`` on timeout."""
        sock = self._sock if self._sock is not None else self._open()
        sock.send(payload)
        if sock.poll(timeout_ms, zmq.POLLIN) == 0:
            self._open()
            return None
        return sock.recv()

    def ping(self, timeout_ms: int = 1000) -> bool:
        return self.request(encode_ping(), timeout_ms) is not None

    def set_streaming_mode(self, enabled: bool, timeout_ms: int = 1000) -> bool:
        return self.request(encode_streaming_mode(enabled), timeout_ms) is not None

    def set_streaming_mode_continuous(
        self, space_filter: str = "jointSpace", timeout_ms: int = 1000
    ) -> bool:
        return (
            self.request(encode_streaming_mode_continuous(space_filter), timeout_ms)
            is not None
        )

    def zero_calibration(
        self, motor_id: int | None = None, timeout_ms: int = 2000
    ) -> bool:
        return self.request(encode_zero_calibration(motor_id), timeout_ms) is not None

    def homing(self, start: bool = True, timeout_ms: int = 2000) -> bool:
        return self.request(encode_homing(start), timeout_ms) is not None


class Publisher:
    """Streamed commands, newest only: each socket keeps one pending frame
    (``CONFLATE``), so a driver that stalls receives the latest setpoint
    when it resumes, never a backlog of stale ones."""

    def __init__(
        self,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        context: zmq.Context | None = None,
    ) -> None:
        self._owns_context = context is None
        self._context = context or zmq.Context()
        self._endpoints = (hand_streaming_endpoint, wrist_streaming_endpoint)
        self._hand: zmq.Socket | None = None
        self._wrist: zmq.Socket | None = None

    def connect(self) -> Publisher:
        self._hand = self._open(self._endpoints[0])
        self._wrist = self._open(self._endpoints[1])
        return self

    def _open(self, endpoint: str) -> zmq.Socket:
        sock = self._context.socket(zmq.PUB)
        sock.setsockopt(zmq.LINGER, 0)
        sock.setsockopt(zmq.CONFLATE, 1)
        sock.connect(endpoint)
        return sock

    def disconnect(self) -> None:
        for sock in (self._hand, self._wrist):
            if sock is not None:
                sock.close(linger=0)
        self._hand = self._wrist = None
        if self._owns_context:
            self._context.term()

    @staticmethod
    def _send(sock: zmq.Socket | None, payload: bytes) -> None:
        """Hands the frame to the socket. A PUB never reports what a peer
        received: a setpoint sent before the driver's subscription completed,
        or superseded before the driver read it, is gone without a trace."""
        if sock is None:
            raise RuntimeError("publisher not connected")
        sock.send(payload, zmq.NOBLOCK)

    def send_rotary_command(
        self,
        positions: Sequence[int],
        torques: Sequence[int],
        velocities: Sequence[int] | None = None,
    ) -> None:
        self._send(self._hand, encode_rotary_command(positions, torques, velocities))

    def send_linear_command(
        self, positions: Sequence[int], speeds: Sequence[int]
    ) -> None:
        self._send(self._wrist, encode_linear_command(positions, speeds))

    def send_hand_command(
        self,
        pose: Mapping[str, Sequence[float]],
        degrees: bool = False,
        torque: float | Sequence[float] = 0.45,
        velocity_saturation: float = 1.0,
    ) -> None:
        self._send(
            self._hand, encode_hand_command(pose, degrees, torque, velocity_saturation)
        )

    def send_wrist_command(
        self,
        positions: Sequence[float],
        velocity_norm: Sequence[float],
        degrees: bool = False,
    ) -> None:
        self._send(self._wrist, encode_wrist_command(positions, velocity_norm, degrees))


class Subscriber:
    """The status stream. The receive buffer is kept short so a reader that
    falls behind sees recent frames, not a backlog; a socket silent for
    ``reconnect_after_s`` is reopened."""

    def __init__(
        self,
        status_endpoint: str,
        receive_hwm: int = 8,
        reconnect_after_s: float = DEFAULT_RECONNECT_AFTER_S,
        context: zmq.Context | None = None,
    ) -> None:
        self._owns_context = context is None
        self._context = context or zmq.Context()
        self._endpoint = status_endpoint
        self._receive_hwm = receive_hwm
        self._reconnect_after_s = reconnect_after_s
        self._sock: zmq.Socket | None = None
        self._last_frame_at = 0.0

    def connect(self) -> Subscriber:
        self._open()
        return self

    def _open(self) -> zmq.Socket:
        if self._sock is not None:
            self._sock.close(linger=0)
        sock = self._context.socket(zmq.SUB)
        sock.setsockopt(zmq.RCVHWM, self._receive_hwm)
        sock.connect(self._endpoint)
        sock.setsockopt(zmq.SUBSCRIBE, b"")
        self._sock = sock
        self._last_frame_at = time.monotonic()
        return sock

    @property
    def socket(self) -> zmq.Socket | None:
        """The SUB socket, for a caller that drains it on its own poller."""
        return self._sock

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close(linger=0)
            self._sock = None
        if self._owns_context:
            self._context.term()

    def receive(self, timeout_ms: int = 100) -> Status | None:
        """The next status frame within ``timeout_ms``, else ``None``."""
        sock = self._sock if self._sock is not None else self._open()
        if sock.poll(timeout_ms, zmq.POLLIN) == 0:
            if time.monotonic() - self._last_frame_at > self._reconnect_after_s:
                self._open()
            return None
        data = sock.recv()
        self._last_frame_at = time.monotonic()
        return parse_status_message(data)

    def try_receive(self) -> Status | None:
        return self.receive(0)
