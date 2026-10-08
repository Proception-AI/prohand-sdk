#!/usr/bin/env python3
"""
ProHand SDK Demo: Rerun logger for every message the firmware publishes.

Streams an eased four-finger curl over the hand streaming socket and logs the
whole status stream to Rerun (rerun.io), time-aligned: rotary feedback (position,
velocity, load, temperature, voltage), the commanded-target echo, per-actuator
tracking error, linear feedback and targets, joint-space targets in radians, IMU,
bus power, warnings and state transitions.

    prohand-rerun --duration 20

Uses `try_recv_message()`, which returns a typed frame per message kind — so a
field can only be read off the kind that carries it. Prints a per-kind frame
histogram at exit.

Requires `rerun-sdk` (the demo's `rerun` extra).
"""

import argparse
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .utils import DemoBase

# `send_hand_streams` takes 20 joint angles: 5 fingers x [Abd, MCP, PIP, DIP].
FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")
JOINT_NAMES = ("abd", "mcp", "pip", "dip")

# Rotary feedback and targets are raw FT3950 encoder counts; linear is 0.01 mm.
# Neither is degrees, so both are logged in their own units.
LINEAR_COUNT_TO_MM = 0.01


def _platform_dir() -> Optional[str]:
    """This host's published driver/<platform>/ directory name, or None."""
    machine = platform.machine()
    if platform.system() == "Darwin":
        return "macos-arm64"
    if platform.system() == "Linux":
        return "linux-arm64" if machine in ("aarch64", "arm64") else "linux-x64"
    return None


def _find_driver_bin() -> Optional[str]:
    """Locate the hand driver binary.

    Search order: $PROHAND_DRIVER_BIN, then the published SDK layout
    (driver/<platform>/), then the monorepo workspace target/ (dev builds).
    """
    name = "prohand-headless-ipc-host"
    env = os.environ.get("PROHAND_DRIVER_BIN")
    if env and Path(env).is_file():
        return env
    # rerun_log.py → prohand_demo → src → python → demo → sdk → <root>
    # (the SDK root when published; the workspace root during development).
    root = Path(__file__).resolve().parents[5]
    candidates = []
    plat = _platform_dir()
    if plat:
        candidates.append(root / "driver" / plat / name)  # published SDK
    candidates += [root / "target" / "release" / name, root / "target" / "debug" / name]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    # Fallback: any published platform dir (e.g. unrecognized arch label).
    for candidate in sorted(root.glob(f"driver/*/{name}")):
        if candidate.is_file():
            return str(candidate)
    return None


def _tmux_has_session(name: str) -> bool:
    return (
        subprocess.run(
            ["tmux", "has-session", "-t", name], capture_output=True
        ).returncode
        == 0
    )


def min_jerk(t: float) -> float:
    """Minimum-jerk easing on [0, 1] — zero velocity and acceleration at both ends."""
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (10.0 - 15.0 * t + 6.0 * t * t)


def curl_pose(phase: float, curl_deg: float, include_thumb: bool) -> List[float]:
    """20-joint pose for an eased curl at `phase` in [0, 1] (0 = flat, 1 = curled).

    Abduction stays at zero; the curl drives MCP/PIP/DIP of the four fingers so
    the pose is safe on both a Gen 1 and a Gen 2 hand.
    """
    angle = math.radians(curl_deg * min_jerk(phase))
    pose = [0.0] * 20
    first = 0 if include_thumb else 1
    for finger in range(first, 5):
        for joint in (1, 2, 3):  # MCP, PIP, DIP
            pose[finger * 4 + joint] = angle
    return pose


class RerunLogDemo(DemoBase):
    """Log ProHand rotary/linear feedback and target echo to Rerun."""

    def __init__(self):
        super().__init__("ProHand → Rerun status logger")

    def _wait_connected(self, client, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if client.is_connected():
                return True
            time.sleep(0.1)
        return client.is_connected()

    def _ensure_driver(self) -> Tuple[bool, Optional[str]]:
        """Launch the hand driver in a detached tmux session if not already up.

        Returns `(ok, session)`: `ok` is whether to keep waiting for a
        connection; `session` is the tmux session *we* started (to kill on
        exit) or `None` if we reused an existing one / couldn't launch.
        """
        if shutil.which("tmux") is None:
            self.error(
                "tmux not found — install tmux, or start the driver yourself and pass --no-launch"
            )
            return (False, None)
        session = "prohand"
        if _tmux_has_session(session):
            self.info(f"reusing existing driver tmux session '{session}'")
            return (True, None)
        bin_path = _find_driver_bin()
        if bin_path is None:
            self.error(
                "driver binary not found. Expected driver/<platform>/prohand-headless-ipc-host "
                "in the SDK; set PROHAND_DRIVER_BIN to its path, or start the driver yourself "
                "and re-run with --no-launch."
            )
            return (False, None)
        # `read` keeps the pane open after the driver exits so a crash or a
        # USB-claim failure stays visible when attaching.
        cmd = f'RUST_LOG=info {bin_path}; echo "[driver exited $?]"; read'
        subprocess.run(["tmux", "new-session", "-d", "-s", session, cmd], check=True)
        self.info(
            f"launched driver in tmux session '{session}'  (attach: tmux attach -t {session})"
        )
        return (True, session)

    def run(self, args) -> int:
        self.banner()

        try:
            import rerun as rr
        except ImportError as e:
            self.error(f"missing dependency: {e}")
            self.info("Install with: uv pip install rerun-sdk")
            return 1

        # `rr.Scalar` was renamed `rr.Scalars` in newer Rerun — accept either.
        Scalar = getattr(rr, "Scalars", None) or getattr(rr, "Scalar")

        # `set_time_seconds` → `set_time(timestamp=)` in Rerun 0.23; support both.
        def set_wallclock(t: float) -> None:
            try:
                rr.set_time("wallclock", timestamp=t)
            except (AttributeError, TypeError):
                getattr(rr, "set_time_seconds")("wallclock", t)

        self.section(f"Connecting to {args.command_endpoint}")
        client = self.sdk.ProHandClient(
            args.command_endpoint,
            args.status_endpoint,
            args.hand_streaming_endpoint,
            args.wrist_streaming_endpoint,
        )

        # Give any already-running driver a moment before launching our own.
        launched_session: Optional[str] = None
        if not self._wait_connected(client, 2.0) and args.launch:
            ok, launched_session = self._ensure_driver()
            if not ok:
                client.close()
                return 1
            self.info("waiting for driver (USB detect + firmware handshake, ~10s)...")
            self._wait_connected(client, 15.0)

        def stop_driver() -> None:
            if launched_session and not args.keep_driver:
                self.info(f"stopping driver (tmux session '{launched_session}')")
                subprocess.run(
                    ["tmux", "kill-session", "-t", launched_session],
                    capture_output=True,
                )

        if not client.is_connected():
            self.error(
                "no connection — driver didn't come up"
                if args.launch
                else "no connection — start the driver, or drop --no-launch to auto-start it"
            )
            client.close()
            stop_driver()
            return 1
        self.success(f"connected (SDK {self.sdk.get_version()})")

        # A `--save` path records to a native Rerun `.rrd` (reopen later with
        # `rerun <file>.rrd`); otherwise stream live to the viewer.
        rr.init("prohand_status", spawn=(args.spawn and not args.save))
        if args.save:
            rr.save(args.save)
            self.info(f"recording to {args.save}")

        # Measured vs commanded on top, tracking error and stream health below.
        # Best-effort — older Rerun without the blueprint API keeps auto-layout.
        try:
            import rerun.blueprint as rrb

            rr.send_blueprint(
                rrb.Blueprint(
                    rrb.Vertical(
                        rrb.Horizontal(
                            rrb.TimeSeriesView(
                                origin="/rotary/position",
                                name="Rotary measured (counts)",
                            ),
                            rrb.TimeSeriesView(
                                origin="/rotary/target",
                                name="Rotary target echo (counts)",
                            ),
                        ),
                        rrb.Horizontal(
                            rrb.TimeSeriesView(
                                origin="/rotary/tracking_error", name="Tracking error"
                            ),
                            rrb.TimeSeriesView(
                                origin="/hand", name="Joint space (deg)"
                            ),
                        ),
                        rrb.Horizontal(
                            rrb.TimeSeriesView(origin="/imu", name="IMU"),
                            rrb.TimeSeriesView(origin="/power", name="Bus power"),
                            rrb.TextLogView(origin="/alerts", name="Warnings"),
                        ),
                        rrb.TimeSeriesView(
                            origin="/meta/frames", name="Frames by kind"
                        ),
                        row_shares=[3, 3, 2, 1],
                    ),
                    collapse_panels=True,
                )
            )
        except Exception as e:
            self.info(f"(default layout; blueprint unavailable: {e})")

        if args.motion:
            self.section("Enabling streaming mode")
            client.set_streaming_mode(True)
            if not client.wait_for_streaming_ready(timeout=10.0):
                self.error("streaming mode never reached Running state")
                client.close()
                stop_driver()
                return 1
            self.success("streaming ready")

        sdk = self.sdk
        counts: dict = {}
        # Latest rotary feedback and target, so tracking error can be logged
        # against whichever of the two interleaved streams arrives second.
        last_position: Optional[List[int]] = None
        last_target: Optional[List[int]] = None
        alerts: List[str] = []

        def log_series(prefix: str, values, scale: float = 1.0) -> None:
            for i, value in enumerate(values):
                rr.log(f"{prefix}/{i:02d}", Scalar(value * scale))

        def log_frame(frame) -> None:
            nonlocal last_position, last_target
            name = type(frame).__name__
            counts[name] = counts.get(name, 0) + 1
            set_wallclock(time.time())
            rr.log(f"meta/frames/{name}", Scalar(counts[name]))

            if isinstance(frame, sdk.RotaryStatusFrame):
                last_position = frame.positions
                log_series("rotary/position", frame.positions)
                log_series("rotary/velocity", frame.velocities)
                log_series("rotary/load", frame.torques)
                log_series("rotary/temperature_c", frame.temperatures_c)
                log_series("rotary/voltage", frame.voltages)
            elif isinstance(frame, sdk.RotaryTargetFrame):
                last_target = frame.positions
                log_series("rotary/target", frame.positions)
                log_series("rotary/target_torque_cap", frame.torque_caps)
                log_series("rotary/target_velocity_cap", frame.velocity_caps)
            elif isinstance(frame, sdk.LinearStatusFrame):
                log_series("linear/position_mm", frame.positions, LINEAR_COUNT_TO_MM)
                log_series("linear/current_ma", frame.currents_ma)
                log_series("linear/speed", frame.speeds)
                log_series("linear/temperature_c", frame.temperatures_c)
            elif isinstance(frame, sdk.LinearTargetFrame):
                log_series("linear/target_mm", frame.positions, LINEAR_COUNT_TO_MM)
            elif isinstance(frame, sdk.JointFrame):
                # Joint space is the one stream already in real units.
                group = "wrist" if frame.is_wrist else "hand"
                stream = "target" if frame.is_target else "feedback"
                log_series(
                    f"{group}/{stream}_deg",
                    [math.degrees(p) for p in frame.positions_rad],
                )
                log_series(f"{group}/{stream}_vel_or_tau", frame.vel_or_tau)
            elif isinstance(frame, sdk.ImuFrame):
                log_series("imu/accel_mps2", frame.accel_mps2)
                log_series("imu/gyro_rps", frame.gyro_rps)
                log_series("imu/quaternion_wxyz", frame.quaternion_wxyz)
                rr.log("imu/temperature_c", Scalar(frame.temperature_c))
            elif isinstance(frame, sdk.PowerFrame):
                rr.log("power/bus_voltage_mv", Scalar(frame.bus_voltage_mv))
                rr.log("power/current_ma", Scalar(frame.current_ma))
                rr.log("power/power_mw", Scalar(frame.power_mw))
            elif isinstance(frame, sdk.AlertFrame):
                detail = (
                    f"{frame.severity.name} {frame.source.name} code={frame.code} "
                    f"detail={frame.detail} actuator={frame.actuator} "
                    f"thermal={frame.thermal_event.name}"
                )
                alerts.append(detail)
                rr.log("alerts", rr.TextLog(detail))
                self.warning(f"alert: {detail}")
            elif isinstance(frame, sdk.StateFrame):
                rr.log(
                    f"state/{frame.kind.name.lower()}",
                    rr.TextLog(f"code={frame.code} detail={frame.detail}"),
                )
                rr.log(f"state/{frame.kind.name.lower()}/code", Scalar(frame.code))
            elif isinstance(frame, sdk.HandednessFrame):
                self.info(f"handedness: {frame.handedness.name}")

            if last_position and last_target:
                log_series(
                    "rotary/tracking_error",
                    [t - p for t, p in zip(last_target, last_position)],
                )

        self.section(
            f"Logging {'+ streaming curl ' if args.motion else ''}— Ctrl+C to stop"
        )
        period = 1.0 / max(args.rate_hz, 1e-6)
        start = time.time()
        next_send = start
        # --velocity is a raw 0-255 saturation count; the SDK now takes it
        # normalized.
        velocity_norm = args.velocity / 255.0
        try:
            while args.duration <= 0 or time.time() - start < args.duration:
                now = time.time()
                if args.motion and now >= next_send:
                    # Triangle over `--cycle-s`, eased: flat → curled → flat.
                    cycle = (now - start) % args.cycle_s / args.cycle_s
                    phase = 2.0 * cycle if cycle < 0.5 else 2.0 * (1.0 - cycle)
                    pose = curl_pose(phase, args.curl_deg, args.include_thumb)
                    client.send_hand_streams(pose, args.torque, velocity_norm)
                    set_wallclock(now)
                    for f, finger in enumerate(FINGER_NAMES):
                        for j, joint in enumerate(JOINT_NAMES):
                            rr.log(
                                f"hand/command/{finger}/{joint}",
                                Scalar(math.degrees(pose[f * 4 + j])),
                            )
                    next_send += period

                # Drain everything queued so every stream stays current.
                drained = 0
                while True:
                    frame = client.try_recv_message()
                    if frame is None:
                        break
                    log_frame(frame)
                    drained += 1
                if drained == 0:
                    time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            if args.motion:
                # Park the hand flat and hand the driver back to command mode.
                try:
                    client.send_hand_streams([0.0] * 20, args.torque, velocity_norm)
                    time.sleep(0.3)
                    client.set_streaming_mode(False)
                except Exception as e:
                    self.warning(f"could not park the hand: {e}")

            self.section("Frames by kind")
            for name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
                print(f"  {name:<20} {count}")
            if alerts:
                self.warning(f"{len(alerts)} alert(s):")
                for alert in alerts[-10:]:
                    print(f"  {alert}")
            client.close()
            stop_driver()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Log ProHand status streams to Rerun",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--command-endpoint", default="ipc:///tmp/prohand-commands.ipc")
    parser.add_argument("--status-endpoint", default="ipc:///tmp/prohand-status.ipc")
    parser.add_argument(
        "--hand-streaming-endpoint", default="ipc:///tmp/prohand-hand-streaming.ipc"
    )
    parser.add_argument(
        "--wrist-streaming-endpoint", default="ipc:///tmp/prohand-wrist-streaming.ipc"
    )
    parser.add_argument(
        "--duration", type=float, default=0.0, help="seconds to log (0 = until Ctrl+C)"
    )
    parser.add_argument(
        "--no-motion",
        dest="motion",
        action="store_false",
        help="log passively instead of streaming a curl (no streaming mode, no commands)",
    )
    parser.add_argument(
        "--curl-deg", type=float, default=18.0, help="peak MCP/PIP/DIP curl angle"
    )
    parser.add_argument(
        "--cycle-s", type=float, default=4.0, help="seconds per curl-and-release cycle"
    )
    parser.add_argument("--rate-hz", type=float, default=100.0, help="streaming rate")
    parser.add_argument("--torque", type=float, default=0.45, help="normalized torque")
    parser.add_argument(
        "--velocity",
        type=int,
        default=50,
        help="servo velocity cap in deg/s (0 = firmware default)",
    )
    parser.add_argument(
        "--include-thumb", action="store_true", help="curl the thumb as well"
    )
    parser.add_argument(
        "--no-spawn",
        dest="spawn",
        action="store_false",
        help="don't auto-launch the Rerun viewer (log to the default sink instead)",
    )
    parser.add_argument(
        "--no-launch",
        dest="launch",
        action="store_false",
        help="don't auto-start the driver; connect to an already-running one",
    )
    parser.add_argument(
        "--keep-driver",
        action="store_true",
        help="leave the auto-started driver's tmux session running on exit",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        default=None,
        help="record to a Rerun .rrd file instead of the live viewer "
        "(reopen with `rerun PATH`)",
    )
    return RerunLogDemo().run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
