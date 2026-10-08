#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Predefined Keyframe Motions

Plays the same built-in showcase sequences the diagnostic GUI's Keyframes tab
offers: an abduction spread/squeeze pulse, a 1-to-5 finger count, a finger
ripple, a rock-on sign, and a fist with a wrist wave.

The interpolation engine mirrors the GUI's: each keyframe declares a transition
duration, a hold duration and an easing profile, and playback streams the
sampled pose at a fixed rate. Sequences here are edit-and-run examples — copy
the pose constants and build your own.
"""

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .utils import DemoBase

# Playback streams at this rate, matching the GUI's 20 ms send interval.
SEND_INTERVAL_S = 0.02

# Defaults chosen to match the diagnostic GUI's keyframe editor, so a sequence
# looks the same here as it does there: 50% torque and a servo velocity cap of
# 50 deg/s (prohand_config DEFAULT_VELOCITY, which is also the GUI's default).
#
# The velocity is sent explicitly rather than as `0` ("use the firmware
# DEFAULT_VELOCITY"). Firmware honors `0` correctly as of the process_hand_command
# fix, but older images assigned velocity_saturation unconditionally, so a `0`
# reached the servos as a velocity of zero and the fingers did not move at all.
# Sending 50 explicitly keeps the demo working on those hands too.
DEFAULT_TORQUE = 0.50
DEFAULT_HAND_VELOCITY = 50

# Servo envelope (prohand_config hw::rotary). A keyframe whose travel/transition
# exceeds the commanded cap cannot be tracked: playback re-targets every 20 ms,
# so the servo is cut off mid-move and the pose is never reached. The GUI's
# built-in template is over-budget at the default 50 deg/s -- see --fit-speed.
MAXIMUM_VELOCITY_DEG_S = 110

# Conservative joint limits: the intersection of the Gen 1 (v1.8) and Gen 2
# finger ROMs, so a sequence is safe on either hand without querying which one
# is attached. Degrees, per finger, as [Abd, MCP, PIP, DIP].
#
# Joint space is anatomical and identical for a left and a right hand: positive
# abduction splays a finger toward the thumb on both. The Gen 1 asymmetry (index
# reaches further positive, pinky further negative) is finger geometry, not
# handedness. Mirroring is absorbed entirely by HandConfig's
# actuator_index_to_tendon map, which exchanges every adjacent servo pair for a
# right hand -- so nothing here needs to know which hand is attached.
FINGER_LIMITS_DEG: List[Tuple[List[float], List[float]]] = [
    ([0.0, -20.0, -5.0, -10.0], [90.0, 40.0, 70.0, 90.0]),  # thumb
    ([-15.0, -15.0, -20.0, 0.0], [25.0, 90.0, 90.0, 90.0]),  # index
    ([-15.0, -15.0, -20.0, 0.0], [15.0, 90.0, 90.0, 90.0]),  # middle
    ([-15.0, -15.0, -20.0, 0.0], [15.0, 90.0, 90.0, 90.0]),  # ring
    ([-25.0, -15.0, -20.0, 0.0], [15.0, 90.0, 90.0, 90.0]),  # pinky
]


# Wrist [Yaw, Pitch] limits in degrees; identical on both wrist variants.
WRIST_LIMITS_DEG: Tuple[List[float], List[float]] = ([-30.0, -30.0], [30.0, 65.0])

FINGER_NAMES = ("Thumb", "Index", "Middle", "Ring", "Pinky")


# ============================================================================
# EASING
# ============================================================================


def ease(profile: str, t: float) -> float:
    """Map raw transition progress in [0, 1] to eased progress."""
    t = min(max(t, 0.0), 1.0)
    if profile == "linear":
        return t
    if profile == "ease_in":
        return t * t
    if profile == "ease_out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if profile == "smooth":  # smoothstep
        return t * t * (3.0 - 2.0 * t)
    if profile == "min_jerk":
        return t * t * t * (10.0 - 15.0 * t + 6.0 * t * t)
    raise ValueError(f"unknown transition profile: {profile}")


PROFILES = ("linear", "ease_in", "ease_out", "smooth", "min_jerk")


# ============================================================================
# POSES
# ============================================================================


@dataclass
class Pose:
    """A full commanded hand pose: 5 fingers x 4 joints, plus wrist yaw/pitch.

    Angles are radians. Finger joints are ordered [Abd, MCP, PIP, DIP].
    """

    fingers_rad: List[List[float]]
    wrist_rad: List[float]

    @staticmethod
    def from_degrees(fingers_deg: List[List[float]], wrist_deg: List[float]) -> "Pose":
        return Pose(
            fingers_rad=[[math.radians(a) for a in f] for f in fingers_deg],
            wrist_rad=[math.radians(a) for a in wrist_deg],
        )

    def clamped(self) -> "Pose":
        """Clamp every joint into the safe ROM. Protects hardware from bad poses."""
        fingers = []
        for f, (lo_deg, hi_deg) in enumerate(FINGER_LIMITS_DEG):
            joints = []
            for j in range(4):
                lo, hi = math.radians(lo_deg[j]), math.radians(hi_deg[j])
                joints.append(min(max(self.fingers_rad[f][j], lo), hi))
            fingers.append(joints)
        lo_deg, hi_deg = WRIST_LIMITS_DEG
        wrist = [
            min(
                max(self.wrist_rad[j], math.radians(lo_deg[j])), math.radians(hi_deg[j])
            )
            for j in range(2)
        ]
        return Pose(fingers_rad=fingers, wrist_rad=wrist)

    def lerp(self, other: "Pose", t: float) -> "Pose":
        return Pose(
            fingers_rad=[
                [a + (b - a) * t for a, b in zip(fa, fb)]
                for fa, fb in zip(self.fingers_rad, other.fingers_rad)
            ],
            wrist_rad=[
                a + (b - a) * t for a, b in zip(self.wrist_rad, other.wrist_rad)
            ],
        )

    def flat_fingers(self) -> List[float]:
        """Flatten to the 20-float layout send_hand_command() expects."""
        return [angle for finger in self.fingers_rad for angle in finger]


# Pose vocabulary, in degrees as [Abd, MCP, PIP, DIP] — shared with the GUI's
# built-in template so the motions look identical.
STRAIGHT = [0.0, 0.0, 0.0, 0.0]
CURLED = [0.0, 80.0, 75.0, 65.0]
HALF = [0.0, 45.0, 40.0, 30.0]
THUMB_OPEN = [15.0, 0.0, 0.0, 0.0]
THUMB_TUCKED = [45.0, 30.0, 45.0, 55.0]
THUMB_WRAPPED = [50.0, 35.0, 50.0, 60.0]


def abd(base: List[float], angle_deg: float) -> List[float]:
    """`base` with its abduction replaced. Positive splays toward the thumb."""
    return [angle_deg, base[1], base[2], base[3]]


HOME_FINGERS = [THUMB_OPEN, STRAIGHT, STRAIGHT, STRAIGHT, STRAIGHT]
OPEN_SPREAD = [
    [30.0, 0.0, 0.0, 0.0],
    abd(STRAIGHT, 15.0),
    abd(STRAIGHT, 5.0),
    abd(STRAIGHT, -5.0),
    abd(STRAIGHT, -15.0),
]
FIST = [THUMB_WRAPPED, CURLED, CURLED, CURLED, CURLED]

HOME_POSE = Pose.from_degrees(HOME_FINGERS, [0.0, 0.0]).clamped()


# ============================================================================
# KEYFRAMES
# ============================================================================


@dataclass
class Keyframe:
    """One waypoint: ease into `pose` over `transition_s`, then hold `hold_s`."""

    name: str
    pose: Pose
    transition_s: float
    hold_s: float
    profile: str = "smooth"
    # Per-keyframe finger velocity cap (0 = firmware default) and wrist speed.
    hand_velocity: int = DEFAULT_HAND_VELOCITY
    torque: float = DEFAULT_TORQUE


def _kf(
    name: str,
    fingers_deg: List[List[float]],
    wrist_deg: List[float],
    transition_s: float,
    hold_s: float,
    profile: str = "smooth",
) -> Keyframe:
    return Keyframe(
        name=name,
        pose=Pose.from_degrees(fingers_deg, wrist_deg).clamped(),
        transition_s=transition_s,
        hold_s=hold_s,
        profile=profile,
    )


# Each group is independently playable via --sequence; "template" is all of them
# back to back, matching the GUI's built-in showcase template.
SEQUENCE_GROUPS: Dict[str, List[Keyframe]] = {
    "abduction": [
        _kf("home", HOME_FINGERS, [0.0, 0.0], 1.2, 0.4),
        _kf("spread", OPEN_SPREAD, [0.0, 0.0], 0.8, 0.5),
        _kf(
            "squeeze",
            [
                [10.0, 0.0, 0.0, 0.0],
                abd(STRAIGHT, -10.0),
                abd(STRAIGHT, -5.0),
                abd(STRAIGHT, 5.0),
                abd(STRAIGHT, 10.0),
            ],
            [0.0, 0.0],
            0.6,
            0.3,
        ),
        _kf("spread 2", OPEN_SPREAD, [0.0, 0.0], 0.6, 0.3),
    ],
    "count": [
        _kf(
            "one",
            [THUMB_TUCKED, STRAIGHT, CURLED, CURLED, CURLED],
            [0.0, 0.0],
            0.9,
            0.6,
        ),
        _kf(
            "two",
            [THUMB_TUCKED, STRAIGHT, STRAIGHT, CURLED, CURLED],
            [0.0, 0.0],
            0.5,
            0.5,
        ),
        _kf(
            "three",
            [THUMB_TUCKED, STRAIGHT, STRAIGHT, STRAIGHT, CURLED],
            [0.0, 0.0],
            0.5,
            0.5,
        ),
        _kf(
            "four",
            [THUMB_TUCKED, STRAIGHT, STRAIGHT, STRAIGHT, STRAIGHT],
            [0.0, 0.0],
            0.5,
            0.5,
        ),
        _kf("five", OPEN_SPREAD, [0.0, 0.0], 0.6, 0.8),
    ],
    "wave": [
        _kf(
            "wave a",
            [THUMB_OPEN, HALF, HALF, STRAIGHT, STRAIGHT],
            [0.0, 0.0],
            0.4,
            0.1,
            "min_jerk",
        ),
        _kf(
            "wave b",
            [THUMB_OPEN, STRAIGHT, HALF, HALF, STRAIGHT],
            [0.0, 0.0],
            0.35,
            0.1,
            "min_jerk",
        ),
        _kf(
            "wave c",
            [THUMB_OPEN, STRAIGHT, STRAIGHT, HALF, HALF],
            [0.0, 0.0],
            0.35,
            0.1,
            "min_jerk",
        ),
        _kf("wave out", HOME_FINGERS, [0.0, 0.0], 0.4, 0.2, "min_jerk"),
    ],
    "rock-on": [
        _kf(
            "rock on",
            [THUMB_TUCKED, abd(STRAIGHT, 15.0), CURLED, CURLED, abd(STRAIGHT, -15.0)],
            [0.0, 0.0],
            0.8,
            1.0,
        ),
    ],
    "fist-wrist": [
        _kf("fist", FIST, [0.0, 0.0], 0.9, 0.6),
        _kf("wave left", FIST, [15.0, 0.0], 0.5, 0.1),
        _kf("wave right", FIST, [-15.0, 0.0], 0.5, 0.1),
        _kf("home", HOME_FINGERS, [0.0, 0.0], 1.2, 0.5, "min_jerk"),
    ],
}

TEMPLATE_ORDER = ("abduction", "count", "wave", "rock-on", "fist-wrist")


def sequence(name: str) -> List[Keyframe]:
    """Resolve a --sequence name to its keyframe list."""
    if name == "template":
        return [kf for group in TEMPLATE_ORDER for kf in SEQUENCE_GROUPS[group]]
    return SEQUENCE_GROUPS[name]


SEQUENCE_NAMES = ("template",) + tuple(SEQUENCE_GROUPS)


# ============================================================================
# MOTION SAMPLER
# ============================================================================


@dataclass
class Segment:
    """A transition from `start` to a keyframe's pose, then a hold."""

    start: Pose
    keyframe: Keyframe

    @property
    def duration_s(self) -> float:
        return self.keyframe.transition_s + self.keyframe.hold_s


def build_segments(start_pose: Pose, keyframes: List[Keyframe]) -> List[Segment]:
    """Chain keyframes so each starts where the previous one ended."""
    segments = []
    prev = start_pose
    for kf in keyframes:
        segments.append(Segment(start=prev, keyframe=kf))
        prev = kf.pose
    return segments


def required_deg_s(seg: Segment) -> float:
    """Peak joint speed this segment's transition demands, deg/s."""
    if seg.keyframe.transition_s <= 0.0:
        return float("inf")
    travel = max(
        max(
            abs(math.degrees(b - a))
            for fa, fb in zip(seg.start.fingers_rad, seg.keyframe.pose.fingers_rad)
            for a, b in zip(fa, fb)
        ),
        max(
            abs(math.degrees(b - a))
            for a, b in zip(seg.start.wrist_rad, seg.keyframe.pose.wrist_rad)
        ),
    )
    return travel / seg.keyframe.transition_s


def fit_to_speed(segments: List[Segment], cap_deg_s: float) -> List[Segment]:
    """Stretch any transition the servos cannot track, preserving pose and easing."""
    out = []
    for seg in segments:
        req = required_deg_s(seg)
        if req > cap_deg_s:
            kf = seg.keyframe
            stretched = kf.transition_s * req / cap_deg_s
            seg = Segment(
                start=seg.start,
                keyframe=Keyframe(
                    kf.name,
                    kf.pose,
                    stretched,
                    kf.hold_s,
                    kf.profile,
                    kf.hand_velocity,
                    kf.torque,
                ),
            )
        out.append(seg)
    return out


def total_duration_s(segments: List[Segment]) -> float:
    return max(sum(s.duration_s for s in segments), 0.001)


def sample(segments: List[Segment], t: float) -> Tuple[int, Pose]:
    """Pose at `t` seconds since sequence start; holds the final pose past the end.

    The single interpolation authority — mirrors the GUI's sample_segments().
    """
    acc = 0.0
    target = len(segments) - 1
    alpha = 1.0
    for i, seg in enumerate(segments):
        seg_end = acc + seg.duration_s
        if t < seg_end:
            target = i
            transition = seg.keyframe.transition_s
            alpha = min((t - acc) / transition, 1.0) if transition > 0.0 else 1.0
            break
        acc = seg_end
    seg = segments[target]
    return target, seg.start.lerp(seg.keyframe.pose, ease(seg.keyframe.profile, alpha))


# ============================================================================
# DEMO
# ============================================================================


@dataclass
class Options:
    command_endpoint: str
    status_endpoint: str
    hand_streaming_endpoint: str
    wrist_streaming_endpoint: str
    sequence: str
    loops: int
    torque: float
    hand_velocity: int
    rate_hz: float
    dry_run: bool
    list_only: bool
    channel: str = "command"
    fit_speed: bool = False
    profile_override: str = ""
    trace: bool = False
    _unused: List[str] = field(default_factory=list)


class KeyframeMotionDemo(DemoBase):
    """Plays predefined keyframe sequences as joint-space poses."""

    def __init__(self):
        super().__init__("ProHand Predefined Keyframe Motions")

    def run(self, opt: Options) -> int:
        self.banner()

        keyframes = sequence(opt.sequence)
        if opt.profile_override:
            keyframes = [
                Keyframe(
                    kf.name,
                    kf.pose,
                    kf.transition_s,
                    kf.hold_s,
                    opt.profile_override,
                    kf.hand_velocity,
                    kf.torque,
                )
                for kf in keyframes
            ]

        segments = build_segments(HOME_POSE, keyframes)
        cap = min(opt.hand_velocity or DEFAULT_HAND_VELOCITY, MAXIMUM_VELOCITY_DEG_S)
        over = [
            (s.keyframe.name, required_deg_s(s))
            for s in segments
            if required_deg_s(s) > cap
        ]
        if over and opt.fit_speed:
            segments = fit_to_speed(segments, cap)
            keyframes = [s.keyframe for s in segments]
        duration = total_duration_s(segments)

        print(
            f"\nSequence '{opt.sequence}': {len(keyframes)} keyframes, {duration:.2f}s per loop"
        )
        for i, kf in enumerate(keyframes):
            print(
                f"  {i:2d}. {kf.name:<10} transition {kf.transition_s:.2f}s "
                f"hold {kf.hold_s:.2f}s  {kf.profile}"
            )

        if over:
            worst = max(r for _, r in over)
            (self.info if opt.fit_speed else self.warning)(
                f"{len(over)}/{len(segments)} transitions exceed the {cap:.0f} deg/s "
                f"cap (peak {worst:.0f} deg/s): "
                + ", ".join(f"{n} {r:.0f}" for n, r in over[:6])
                + ("..." if len(over) > 6 else "")
            )
            if opt.fit_speed:
                self.info(
                    f"--fit-speed stretched them; sequence is now {duration:.2f}s"
                )
            else:
                self.warning(
                    "The servos cannot track these, so those poses will be cut off "
                    "mid-move and the motion will look truncated. Pass --fit-speed to "
                    "stretch the transitions, or raise --hand-velocity (max "
                    f"{MAXIMUM_VELOCITY_DEG_S})."
                )

        if opt.list_only:
            return 0

        print("\nPlayback parameters:")
        print(f"  Loops:          {opt.loops if opt.loops > 0 else 'until Ctrl-C'}")
        print(f"  Torque:         {opt.torque}")
        print(f"  Hand velocity:  {opt.hand_velocity} deg/s")
        print(f"  Sample rate:    {opt.rate_hz} Hz")
        print(f"  Channel:        {opt.channel}")

        if opt.dry_run:
            self.section("Dry run — sampling the trajectory without sending")
            self._trace_trajectory(segments, duration, opt)
            self.success("Trajectory sampled; no commands sent.")
            return 0

        client = None
        try:
            self.section("Connecting to IPC host...")
            client = self.sdk.ProHandClient(
                opt.command_endpoint,
                opt.status_endpoint,
                opt.hand_streaming_endpoint,
                opt.wrist_streaming_endpoint,
            )
            client.send_ping()
            time.sleep(0.2)
            self.success("Connected and ping sent.")

            # Streaming mode also gates the command channel's motion handling, so
            # enable it for both channels — same as the GUI's ensure_streaming_mode.
            self.section("Enabling streaming mode...")
            client.set_streaming_mode(True)
            if not client.wait_for_streaming_ready(timeout=10.0):
                self.error("Streaming did not reach Running state.")
                return 1
            self.success("Streaming ready.")

            self.section("Playing sequence — Ctrl-C to stop and return home")
            self._play(client, segments, duration, opt)
            self.success("Sequence complete.")
            return 0

        except KeyboardInterrupt:
            print()
            self.warning("Interrupted — returning to home pose.")
            if client is not None:
                self._return_home(client, opt)
            return 130
        except Exception as e:  # noqa: BLE001 - demo surfaces any SDK error
            self.error(f"{type(e).__name__}: {e}")
            return 1
        finally:
            if client is not None:
                try:
                    client.set_streaming_mode(False)
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
                client.close()

    def _trace_trajectory(self, segments, duration: float, opt: Options) -> None:
        """Walk the sequence, reporting each keyframe's target pose as it starts.

        Angles are the keyframe's destination, not the mid-transition pose, so
        the table reads as the sequence's intent.
        """
        step = 1.0 / opt.rate_hz
        samples = 0
        last_index = -1
        t = 0.0
        while t < duration:
            index, _ = sample(segments, t)
            if index != last_index:
                kf = segments[index].keyframe
                per_finger = " ".join(
                    f"{name[0]}:{math.degrees(max(joints, key=abs)):>5.0f}"
                    for name, joints in zip(FINGER_NAMES, kf.pose.fingers_rad)
                )
                wrist = ", ".join(f"{math.degrees(w):.0f}" for w in kf.pose.wrist_rad)
                print(
                    f"  t={t:6.2f}s  -> {kf.name:<10} "
                    f"peak/finger[{per_finger}]  wrist[{wrist}] deg"
                )
                last_index = index
            samples += 1
            t += step
        print(f"  {samples} samples over {duration:.2f}s at {opt.rate_hz} Hz")

    def _play(self, client, segments, duration: float, opt: Options) -> None:
        loop = 0
        while opt.loops <= 0 or loop < opt.loops:
            loop += 1
            print(f"  loop {loop}" + ("" if opt.loops <= 0 else f"/{opt.loops}"))
            start = time.monotonic()
            last_index = -1
            while True:
                t = time.monotonic() - start
                if t >= duration:
                    break
                index, pose = sample(segments, t)
                if index != last_index:
                    kf = segments[index].keyframe
                    print(f"    -> {kf.name}")
                    last_index = index
                self._send(client, pose, opt)
                time.sleep(SEND_INTERVAL_S)
            # Settle on the final pose so the hand is not left mid-transition.
            self._send(client, segments[-1].keyframe.pose, opt)
            time.sleep(0.1)

    def _send(self, client, pose: Pose, opt: Options) -> None:
        """Send one sampled pose as joint-space hand + wrist commands.

        `command` (REQ/REP) is the default because it is the only path that
        reaches the driver's host-side IK, which converts joint angles into
        actuator targets. Both channels reach it, so both move the fingers.
        `command` is the default because it is what the diagnostic GUI's keyframe
        playback uses; `stream` is the lower-latency path for high-rate control
        (it drops stale frames instead of round-tripping per command).
        """
        # hand_velocity is a raw 0-255 saturation count; the SDK now takes it
        # normalized.
        velocity = opt.hand_velocity / 255.0
        if opt.channel == "stream":
            client.send_hand_streams(pose.flat_fingers(), opt.torque, velocity)
            client.send_wrist_streams(pose.wrist_rad)
        else:
            client.send_hand_command(pose.flat_fingers(), opt.torque, velocity)
            client.send_wrist_command(pose.wrist_rad)

    def _return_home(self, client, opt: Options) -> None:
        """Ease back to home over ~0.8s instead of snapping."""
        segments = build_segments(
            HOME_POSE, [Keyframe("home", HOME_POSE, 0.8, 0.1, "smooth")]
        )
        duration = total_duration_s(segments)
        start = time.monotonic()
        while True:
            t = time.monotonic() - start
            if t >= duration:
                break
            _, pose = sample(segments, t)
            try:
                self._send(client, pose, opt)
            except Exception:  # noqa: BLE001 - best-effort during shutdown
                return
            time.sleep(SEND_INTERVAL_S)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Play predefined keyframe motion sequences",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--command-endpoint",
        default="ipc:///tmp/prohand-commands.ipc",
        help="ZMQ command endpoint",
    )
    parser.add_argument(
        "--status-endpoint",
        default="ipc:///tmp/prohand-status.ipc",
        help="ZMQ status endpoint",
    )
    parser.add_argument(
        "--hand-streaming-endpoint",
        default="ipc:///tmp/prohand-hand-streaming.ipc",
        help="ZMQ hand streaming endpoint",
    )
    parser.add_argument(
        "--wrist-streaming-endpoint",
        default="ipc:///tmp/prohand-wrist-streaming.ipc",
        help="ZMQ wrist streaming endpoint",
    )
    parser.add_argument(
        "--sequence",
        choices=SEQUENCE_NAMES,
        default="template",
        help="Which predefined sequence to play",
    )
    parser.add_argument(
        "--loops", type=int, default=1, help="Times to repeat (0 = until Ctrl-C)"
    )
    parser.add_argument(
        "--torque",
        type=float,
        default=DEFAULT_TORQUE,
        help="Joint torque, normalized 0.0-1.0",
    )
    parser.add_argument(
        "--hand-velocity",
        type=int,
        default=DEFAULT_HAND_VELOCITY,
        help=(
            "Servo velocity cap in deg/s (1-255). Do NOT pass 0: firmware "
            "applies it verbatim, so 0 freezes the fingers"
        ),
    )
    parser.add_argument(
        "--rate-hz", type=float, default=50.0, help="Trajectory sample rate"
    )
    parser.add_argument(
        "--channel",
        choices=("command", "stream"),
        default="command",
        help=(
            "Transport for the joint-space poses; firmware runs the IK either "
            "way. 'command' (REQ/REP) matches the diagnostic GUI; 'stream' "
            "(PUB/SUB) is lower latency and drops stale frames under load"
        ),
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="",
        help="Override every keyframe's easing profile",
    )
    parser.add_argument(
        "--fit-speed",
        action="store_true",
        help=(
            "Stretch any transition the servos cannot track at --hand-velocity, "
            "so poses are actually reached instead of being cut off mid-move"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sample and print the trajectory without connecting or moving",
    )
    parser.add_argument(
        "--list", action="store_true", help="List the sequence's keyframes and exit"
    )
    args = parser.parse_args()

    if not 0 <= args.hand_velocity <= 255:
        parser.error("--hand-velocity must be in 0..255")

    demo = KeyframeMotionDemo()
    return demo.run(
        Options(
            command_endpoint=args.command_endpoint,
            status_endpoint=args.status_endpoint,
            hand_streaming_endpoint=args.hand_streaming_endpoint,
            wrist_streaming_endpoint=args.wrist_streaming_endpoint,
            sequence=args.sequence,
            loops=args.loops,
            torque=args.torque,
            hand_velocity=args.hand_velocity,
            rate_hz=args.rate_hz,
            dry_run=args.dry_run,
            list_only=args.list,
            channel=args.channel,
            fit_speed=args.fit_speed,
            profile_override=args.profile,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
