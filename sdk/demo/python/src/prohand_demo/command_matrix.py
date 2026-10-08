#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Command Coverage Matrix

Exercises every entry point the Python SDK exposes and reports pass/fail/skip
per command, so a new build can be smoke-tested in one run.

Motion commands send the neutral home pose, so the hand does not swing.  The two
commands that drive the hand against its hard stops — auto-calibration and
homing — are opt-in behind --include-calibration and are skipped by default.

Most checks pass without a driver attached: the client connects lazily and
commands queue, so this validates the bindings and their argument guards even
with no hardware.  Checks that need live telemetry report SKIP instead of FAIL
when the driver is absent.
"""

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from .utils import DemoBase

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# Neutral pose: everything at zero. Safe to command at any time.
NEUTRAL_FINGERS = [0.0] * 20
NEUTRAL_WRIST = [0.0, 0.0]
NEUTRAL_ROTARY = [0.0] * 16
NEUTRAL_LINEAR = [0.0, 0.0]
DEFAULT_TORQUE = 0.3
# Torque accepts a scalar, 5 values (per finger) or 20 (per joint).
PER_FINGER_TORQUE = [0.2, 0.3, 0.3, 0.25, 0.25]
PER_JOINT_TORQUE = [0.25] * 20


@dataclass
class Check:
    """One command's result."""

    category: str
    name: str
    status: str
    detail: str = ""


class CommandMatrixDemo(DemoBase):
    """Runs every SDK command and tabulates the outcome."""

    def __init__(self):
        super().__init__("ProHand SDK Command Coverage Matrix")
        self.checks: List[Check] = []

    # ------------------------------------------------------------------
    # result recording
    # ------------------------------------------------------------------

    def _run(self, category: str, name: str, fn: Callable[[], Optional[str]]) -> bool:
        """Run one check; `fn` returns an optional detail string or raises."""
        try:
            detail = fn() or ""
            self.checks.append(Check(category, name, PASS, detail))
            print(f"  [{PASS}] {name}" + (f" — {detail}" if detail else ""))
            return True
        except Exception as e:  # noqa: BLE001 - a demo reports every failure mode
            detail = f"{type(e).__name__}: {e}"
            self.checks.append(Check(category, name, FAIL, detail))
            print(f"  [{FAIL}] {name} — {detail}")
            return False

    def _skip(self, category: str, name: str, why: str) -> None:
        self.checks.append(Check(category, name, SKIP, why))
        print(f"  [{SKIP}] {name} — {why}")

    def _expect_raises(self, exc_type, fn: Callable[[], object]) -> str:
        """Assert `fn` rejects bad input, so guards are verified not just present."""
        try:
            fn()
        except exc_type as e:
            return f"correctly rejected: {e}"
        except Exception as e:  # noqa: BLE001
            raise AssertionError(
                f"expected {exc_type.__name__}, got {type(e).__name__}: {e}"
            ) from e
        raise AssertionError(f"expected {exc_type.__name__}, but no error was raised")

    # ------------------------------------------------------------------
    # phases
    # ------------------------------------------------------------------

    def _phase_module(self) -> None:
        self.section("Module-level functions")
        sdk = self.sdk
        self._run("module", "get_version", lambda: sdk.get_version())
        self._run(
            "module",
            "discover_usb_devices",
            lambda: f"{len(sdk.discover_usb_devices())} device(s)",
        )
        self._run(
            "module",
            "CalibrationMask",
            lambda: f"ALL=0b{int(sdk.CalibrationMask.ALL):05b}",
        )

    def _phase_lifecycle(self, client) -> None:
        self.section("Lifecycle and liveness")
        self._run(
            "lifecycle", "is_connected", lambda: f"connected={client.is_connected()}"
        )
        self._run(
            "lifecycle",
            "ms_since_last_heartbeat",
            lambda: f"{client.ms_since_last_heartbeat()} ms",
        )
        self._run("lifecycle", "send_ping", lambda: client.send_ping())

    def _phase_guards(self, client) -> None:
        """Argument validation — pure client-side, no driver needed."""
        self.section("Argument guards")
        bad = self.sdk.InvalidArgumentError
        self._run(
            "guards",
            "send_hand_command rejects wrong length",
            lambda: self._expect_raises(
                bad, lambda: client.send_hand_command([0.0] * 19)
            ),
        )
        self._run(
            "guards",
            "send_hand_command rejects a 3-element torque list",
            lambda: self._expect_raises(
                bad, lambda: client.send_hand_command(NEUTRAL_FINGERS, [0.3] * 3)
            ),
        )
        self._run(
            "guards",
            "send_hand_command rejects velocity outside 0.0-1.0",
            lambda: self._expect_raises(
                bad, lambda: client.send_hand_command(NEUTRAL_FINGERS, 0.3, 1.5)
            ),
        )
        self._run(
            "guards",
            "send_rotary_commands rejects wrong length",
            lambda: self._expect_raises(
                bad, lambda: client.send_rotary_commands([0.0] * 15, [0.0] * 16)
            ),
        )
        self._run(
            "guards",
            "send_zero_calibration rejects wrong length",
            lambda: self._expect_raises(
                bad, lambda: client.send_zero_calibration([False] * 15)
            ),
        )
        self._run(
            "guards",
            "send_auto_calibration rejects out-of-range mask",
            lambda: self._expect_raises(
                bad, lambda: client.send_auto_calibration(0xFF)
            ),
        )

    def _phase_commands(self, client) -> None:
        """REQ/REP command channel, neutral pose throughout."""
        self.section("Command channel (REQ/REP)")
        self._run(
            "command",
            "send_rotary_commands",
            lambda: client.send_rotary_commands(NEUTRAL_ROTARY, [DEFAULT_TORQUE] * 16),
        )
        self._run(
            "command",
            "send_linear_commands",
            lambda: client.send_linear_commands(NEUTRAL_LINEAR, [DEFAULT_TORQUE] * 2),
        )
        self._run(
            "command",
            "send_hand_command",
            lambda: client.send_hand_command(NEUTRAL_FINGERS, DEFAULT_TORQUE),
        )
        self._run(
            "command",
            "send_hand_command (velocity_saturation=0.25)",
            lambda: client.send_hand_command(NEUTRAL_FINGERS, DEFAULT_TORQUE, 0.25),
        )
        self._run(
            "command",
            "send_hand_command (per-finger torque)",
            lambda: client.send_hand_command(NEUTRAL_FINGERS, PER_FINGER_TORQUE),
        )
        self._run(
            "command",
            "send_hand_command (per-joint torque)",
            lambda: client.send_hand_command(NEUTRAL_FINGERS, PER_JOINT_TORQUE),
        )
        self._run(
            "command",
            "send_wrist_command",
            lambda: client.send_wrist_command(NEUTRAL_WRIST),
        )
        self._run(
            "command",
            "send_wrist_command (use_profiler=True)",
            lambda: client.send_wrist_command(NEUTRAL_WRIST, True),
        )
        self._run(
            "command",
            "send_zero_calibration (empty mask)",
            lambda: client.send_zero_calibration([False] * 16),
        )

    def _phase_wrist_limits(self, client) -> None:
        self.section("Wrist motion profiler")
        # ERROR_UNSUPPORTED is the documented answer when the SDK was built
        # without the motion-profiler feature — that is a skip, not a failure.
        try:
            client.set_wrist_limits([1.0, 1.0], [5.0, 5.0], [50.0, 50.0])
            self.checks.append(Check("profiler", "set_wrist_limits", PASS))
            print(f"  [{PASS}] set_wrist_limits")
        except Exception as e:  # noqa: BLE001
            if "not supported" in str(e).lower():
                self._skip(
                    "profiler", "set_wrist_limits", "motion-profiler not in build"
                )
            else:
                self.checks.append(Check("profiler", "set_wrist_limits", FAIL, str(e)))
                print(f"  [{FAIL}] set_wrist_limits — {e}")

    def _phase_streaming(self, client, timeout: float) -> bool:
        self.section("Streaming channel (PUB/SUB)")
        self._run(
            "stream",
            "set_streaming_mode(True)",
            lambda: client.set_streaming_mode(True),
        )

        ready = client.wait_for_streaming_ready(timeout=timeout)
        if ready:
            self.checks.append(Check("stream", "wait_for_streaming_ready", PASS))
            print(f"  [{PASS}] wait_for_streaming_ready")
        else:
            self._skip(
                "stream",
                "wait_for_streaming_ready",
                f"driver did not reach Running within {timeout}s",
            )

        self._run(
            "stream", "is_running_state", lambda: f"running={client.is_running_state()}"
        )
        self._run(
            "stream",
            "send_rotary_streams",
            lambda: client.send_rotary_streams(NEUTRAL_ROTARY, [DEFAULT_TORQUE] * 16),
        )
        self._run(
            "stream",
            "send_linear_streams",
            lambda: client.send_linear_streams(NEUTRAL_LINEAR, [DEFAULT_TORQUE] * 2),
        )
        self._run(
            "stream",
            "send_hand_streams",
            lambda: client.send_hand_streams(NEUTRAL_FINGERS, DEFAULT_TORQUE),
        )
        self._run(
            "stream",
            "send_hand_streams (velocity_saturation=0.25)",
            lambda: client.send_hand_streams(NEUTRAL_FINGERS, DEFAULT_TORQUE, 0.25),
        )
        self._run(
            "stream",
            "send_hand_streams (per-finger torque)",
            lambda: client.send_hand_streams(NEUTRAL_FINGERS, PER_FINGER_TORQUE),
        )
        self._run(
            "stream",
            "send_hand_streams (per-joint torque)",
            lambda: client.send_hand_streams(NEUTRAL_FINGERS, PER_JOINT_TORQUE),
        )
        self._run(
            "stream",
            "send_wrist_streams",
            lambda: client.send_wrist_streams(NEUTRAL_WRIST),
        )
        self._run(
            "stream",
            "set_streaming_mode(False)",
            lambda: client.set_streaming_mode(False),
        )
        return ready

    def _phase_status(self, client, seconds: float) -> None:
        self.section(f"Status channel (polling {seconds}s)")
        deadline = time.monotonic() + seconds
        seen = {}
        while time.monotonic() < deadline:
            status = client.try_recv_status()
            if status is not None:
                seen[status.status_type] = seen.get(status.status_type, 0) + 1
            else:
                time.sleep(0.005)

        if not seen:
            self._skip(
                "status", "try_recv_status", "no status received (driver offline?)"
            )
            return

        labels = {
            1: "rotary",
            2: "linear",
            3: "rotary target",
            4: "linear target",
            0: "other",
        }
        detail = ", ".join(f"{labels.get(k, k)}={v}" for k, v in sorted(seen.items()))
        self.checks.append(Check("status", "try_recv_status", PASS, detail))
        print(f"  [{PASS}] try_recv_status — {detail}")

        self._run(
            "status",
            "ms_since_last_heartbeat (after traffic)",
            lambda: f"{client.ms_since_last_heartbeat()} ms",
        )

    def _phase_calibration(self, client, include: bool) -> None:
        self.section("Calibration and homing")
        if not include:
            self._skip(
                "calibration",
                "send_auto_calibration",
                "needs --include-calibration (drives fingers into hard stops)",
            )
            self._skip(
                "calibration",
                "send_homing",
                "needs --include-calibration (moves the hand)",
            )
            return

        mask = self.sdk.CalibrationMask
        self.warning("Auto-calibration and homing will move the hand. Keep it clear.")
        self._run(
            "calibration",
            "send_auto_calibration(ABORT)",
            lambda: client.send_auto_calibration(mask.ABORT),
        )
        self._run(
            "calibration",
            "send_auto_calibration(THUMB)",
            lambda: client.send_auto_calibration(mask.THUMB),
        )
        time.sleep(1.0)
        self._run(
            "calibration",
            "send_auto_calibration(ABORT) to stop",
            lambda: client.send_auto_calibration(mask.ABORT),
        )
        self._run("calibration", "send_homing(True)", lambda: client.send_homing(True))
        time.sleep(1.0)
        self._run(
            "calibration", "send_homing(False)", lambda: client.send_homing(False)
        )

    def _phase_context_manager(self, opt) -> None:
        self.section("Context manager")

        def use_with_block() -> str:
            with self.sdk.ProHandClient(
                opt.command_endpoint,
                opt.status_endpoint,
                opt.hand_streaming_endpoint,
                opt.wrist_streaming_endpoint,
            ) as c:
                c.send_ping()
            return "entered, pinged and closed"

        self._run("lifecycle", "with ProHandClient(...) as c", use_with_block)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    def run(self, opt) -> int:
        self.banner()
        print("\nEndpoints:")
        print(f"  command:         {opt.command_endpoint}")
        print(f"  status:          {opt.status_endpoint}")
        print(f"  hand streaming:  {opt.hand_streaming_endpoint}")
        print(f"  wrist streaming: {opt.wrist_streaming_endpoint}")

        self._phase_module()

        client = None
        try:
            self.section("Creating client")
            client = self.sdk.ProHandClient(
                opt.command_endpoint,
                opt.status_endpoint,
                opt.hand_streaming_endpoint,
                opt.wrist_streaming_endpoint,
            )
            self.success("Client created.")

            self._phase_lifecycle(client)
            self._phase_guards(client)
            self._phase_commands(client)
            self._phase_wrist_limits(client)
            self._phase_streaming(client, opt.streaming_timeout)
            self._phase_status(client, opt.status_seconds)
            self._phase_calibration(client, opt.include_calibration)
        except Exception as e:  # noqa: BLE001
            self.error(f"Aborted: {type(e).__name__}: {e}")
            self.checks.append(Check("fatal", "run", FAIL, str(e)))
        finally:
            if client is not None:
                client.close()

        self._phase_context_manager(opt)
        return self._report()

    def _report(self) -> int:
        passed = sum(c.status == PASS for c in self.checks)
        failed = sum(c.status == FAIL for c in self.checks)
        skipped = sum(c.status == SKIP for c in self.checks)

        print()
        print("=" * 60)
        print(
            f"{len(self.checks)} checks: {passed} passed, {failed} failed, {skipped} skipped"
        )
        print("=" * 60)

        if failed:
            print("\nFailures:")
            for c in self.checks:
                if c.status == FAIL:
                    print(f"  {c.category}/{c.name}: {c.detail}")
        if skipped:
            print("\nSkipped:")
            for c in self.checks:
                if c.status == SKIP:
                    print(f"  {c.category}/{c.name}: {c.detail}")

        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise every ProHand SDK command and report coverage",
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
        "--streaming-timeout",
        type=float,
        default=3.0,
        help="Seconds to wait for the driver to reach Running state",
    )
    parser.add_argument(
        "--status-seconds",
        type=float,
        default=1.0,
        help="Seconds to poll the status channel",
    )
    parser.add_argument(
        "--include-calibration",
        action="store_true",
        help="Also run auto-calibration and homing (MOVES THE HAND — keep it clear)",
    )
    args = parser.parse_args()

    demo = CommandMatrixDemo()
    return demo.run(args)


if __name__ == "__main__":
    sys.exit(main())
