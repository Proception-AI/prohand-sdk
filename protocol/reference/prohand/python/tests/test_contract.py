"""The wire contract, checked in both directions against fixtures the other
side of the protocol wrote.

``fixtures/status_frames.bin`` holds every public status variant as the
driver's own encoder (``prohand-capnp``, internal edition) writes it; this
client must decode each one, header and host time included.

``fixtures/command_frames.bin`` holds every command this client can build;
``prohand-capnp``'s tests decode them with the driver's edition. The test
here keeps that fixture current: run with ``PROHAND_UPDATE_FIXTURES=1`` to
rewrite it after a deliberate change to an encoder.

Both files are a sequence of ``u32 little-endian length, bytes`` records.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

import prohand_client as pc
import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

STATUS_VARIANTS = [
    "pong",
    "handRequestEcho",
    "rotaryState",
    "linearState",
    "handState",
    "rotaryGrpStatus",
    "linearGrpStatus",
    "rotaryGrpTarget",
    "linearGrpTarget",
    "handedness",
    "imuStatus",
    "imuState",
    "timeSyncAck",
    "alert",
    "currentSenseStatus",
    "currentSenseState",
    "handJointTarget",
    "wristJointTarget",
    "handJointStatus",
    "wristJointStatus",
    "handObservedState",
    "handHealth",
    "syncStatus",
]

OPEN_HAND = {finger: [0.1 * (j + 1) for j in range(4)] for finger in pc.FINGERS}


def command_frames() -> list[bytes]:
    """Every command this client builds, with fixed uids and stamps so the
    bytes are the same on every run. Order is the contract with the Rust
    side; append, never reorder."""
    return [
        pc.encode_ping(),
        pc.encode_streaming_mode(False),
        pc.encode_streaming_mode(True),
        pc.encode_streaming_mode_continuous("jointSpace"),
        pc.encode_zero_calibration(),
        pc.encode_zero_calibration(3),
        pc.encode_homing(True),
        pc.encode_rotary_command([i * 10 for i in range(16)], [100] * 16),
        pc.encode_linear_command([1, 2], [3, 4]),
        pc.encode_hand_command(
            OPEN_HAND, torque=0.5, velocity_saturation=0.5, uid=7, timestamp_ms=9
        ),
        pc.encode_wrist_command([0.1, -0.1], [0.5, 1.0], uid=8, timestamp_ms=10),
        # The awkward inputs: a half-way value, angles past 180 degrees, the
        # range ends. prohand-capnp's tests assert the exact integers.
        pc.encode_hand_command(
            {"thumb": [0.3, 0.5, 3.2, -3.2], "index": [1.0, -1.0, 0.0, 0.3]},
            torque=0.3,
            velocity_saturation=0.3,
            uid=11,
            timestamp_ms=12,
        ),
        pc.encode_wrist_command([3.2, -3.2], [0.5, 0.3], uid=13, timestamp_ms=14),
    ]


def read_records(path: Path) -> list[bytes]:
    data = path.read_bytes()
    records = []
    pos = 0
    while pos < len(data):
        (length,) = struct.unpack_from("<I", data, pos)
        pos += 4
        records.append(data[pos : pos + length])
        pos += length
    return records


def write_records(path: Path, records: list[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(struct.pack("<I", len(r)) + r for r in records))


# ── Status: the driver wrote it, this client reads it ───────────────────────


def test_every_public_status_variant_decodes_with_its_header():
    frames = read_records(FIXTURES / "status_frames.bin")
    assert len(frames) == len(STATUS_VARIANTS), (
        "regenerate: cargo test -p prohand-capnp"
    )
    for index, frame in enumerate(frames):
        status = pc.parse_status_message(frame)
        assert status.which == STATUS_VARIANTS[index]
        assert status.header == pc.Header(
            t_device_us=1_000 + index, tick=7, seq=index, boot=3, dropped=1, sync=2
        )
        assert status.t_host_us == 2_000 + index


def test_a_frame_without_a_header_reads_as_unbound_and_unsynced():
    status = pc.prohand_capnp.ProHandStatus.new_message()
    status.pong = None
    parsed = pc.parse_status_message(status.to_bytes_packed())
    assert parsed.which == "pong"
    assert parsed.header == pc.Header()
    assert parsed.t_host_us is None


# ── Commands: this client wrote it, the driver reads it ─────────────────────


def test_command_fixture_is_current():
    path = FIXTURES / "command_frames.bin"
    frames = command_frames()
    if os.environ.get("PROHAND_UPDATE_FIXTURES"):
        write_records(path, frames)
    assert path.is_file(), "run once with PROHAND_UPDATE_FIXTURES=1"
    assert read_records(path) == frames, (
        "an encoder changed its bytes; if that is intended, rerun with "
        "PROHAND_UPDATE_FIXTURES=1 and let prohand-capnp's tests judge the result"
    )


def test_commands_round_trip_through_the_public_schema():
    cmd = pc.prohand_capnp.ProHandCommand
    rotary = cmd.from_bytes_packed(pc.encode_rotary_command([5] * 16, [6] * 16))
    assert [s.velocity for s in rotary.rotaryGrpCommand] == [
        pc.DEFAULT_ROTARY_VELOCITY
    ] * 16
    hand = cmd.from_bytes_packed(
        pc.encode_hand_command(
            {"index": [1.0, 0, 0, 0]}, torque=1.0, velocity_saturation=1.0
        )
    ).handStateCommand
    assert hand.velocitySaturation == 255
    assert hand.index[0].scaledPosition == 5730
    assert hand.index[0].normalizedVelOrTau == 32767
    assert hand.thumb[3].scaledPosition == 0
    degrees = cmd.from_bytes_packed(
        pc.encode_hand_command({"index": [90.0, 0, 0, 0]}, degrees=True)
    ).handStateCommand
    assert degrees.index[0].scaledPosition == 9000
    half = cmd.from_bytes_packed(
        pc.encode_hand_command(
            {"thumb": [3.2, -3.2, 0, 0]}, torque=0.5, velocity_saturation=0.3
        )
    ).handStateCommand
    assert half.thumb[0].normalizedVelOrTau == 16384, "16383.5 rounds away from zero"
    assert half.velocitySaturation == 77, "76.5 rounds away from zero"
    assert half.thumb[0].scaledPosition == 18335, (
        "past 180 degrees is clamped, not wrapped"
    )
    assert half.thumb[1].scaledPosition == -18335
    calib = cmd.from_bytes_packed(pc.encode_zero_calibration(3)).handRequest.zeroCalib
    assert list(calib) == [i == 3 for i in range(16)]
    assert (
        str(
            cmd.from_bytes_packed(
                pc.encode_streaming_mode(True)
            ).handRequest.streamingMode.which()
        )
        == "onDemand"
    )
    assert (
        str(
            cmd.from_bytes_packed(
                pc.encode_streaming_mode_continuous()
            ).handRequest.streamingMode.continuous
        )
        == "jointSpace"
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: pc.encode_rotary_command([0] * 15, [0] * 16),
        lambda: pc.encode_rotary_command([0] * 16, [0] * 16, [0] * 3),
        lambda: pc.encode_linear_command([0], [0]),
        lambda: pc.encode_hand_command({}, torque=[0.1, 0.2]),
        lambda: pc.encode_wrist_command([0.0], [1.0, 1.0]),
        lambda: pc.encode_wrist_command([0.0, 0.0], [1.0]),
    ],
)
def test_wrong_lengths_are_refused_before_anything_is_sent(call):
    with pytest.raises(ValueError):
        call()


# ── Transport: the sockets carry what the encoders made ─────────────────────


def test_service_client_times_out_without_a_driver_and_stays_usable():
    client = pc.ServiceClient("tcp://127.0.0.1:1").connect()
    try:
        assert client.ping(timeout_ms=50) is False
        assert client.ping(timeout_ms=50) is False
    finally:
        client.disconnect()


def test_a_published_command_reaches_a_subscriber_in_process():
    import zmq

    context = zmq.Context()
    sink = context.socket(zmq.SUB)
    sink.bind("inproc://hand")
    sink.setsockopt(zmq.SUBSCRIBE, b"")
    # libzmq 4.3.5 asserts at context teardown when a CONFLATE publisher's
    # inproc peer was never bound, so the wrist endpoint gets a sink too.
    wrist_sink = context.socket(zmq.SUB)
    wrist_sink.bind("inproc://wrist")
    publisher = pc.Publisher(
        "inproc://hand", "inproc://wrist", context=context
    ).connect()
    try:
        # A PUB drops what it sends before the subscription reaches it, so
        # send until the first frame lands.
        for _ in range(50):
            publisher.send_rotary_command([1] * 16, [2] * 16)
            if sink.poll(20, zmq.POLLIN):
                break
        assert sink.poll(0, zmq.POLLIN), "no frame reached the subscriber"
        frame = pc.prohand_capnp.ProHandCommand.from_bytes_packed(sink.recv())
        assert [s.position for s in frame.rotaryGrpCommand] == [1] * 16
    finally:
        publisher.disconnect()
        sink.close(linger=0)
        wrist_sink.close(linger=0)
        context.term()


def test_subscriber_decodes_a_frame_from_a_publisher_in_process():
    import zmq

    context = zmq.Context()
    source = context.socket(zmq.PUB)
    source.bind("inproc://status")
    subscriber = pc.Subscriber("inproc://status", context=context).connect()
    try:
        status = pc.prohand_capnp.ProHandStatus.new_message()
        status.handedness = "left"
        status.init("header").seq = 42
        source.send(status.to_bytes_packed())
        received = subscriber.receive(1000)
        assert received is not None
        assert received.which == "handedness"
        assert str(received.body.handedness) == "left"
        assert received.header.seq == 42
        assert subscriber.receive(10) is None
    finally:
        subscriber.disconnect()
        source.close(linger=0)
        context.term()
