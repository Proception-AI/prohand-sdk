#!/usr/bin/env python3
"""
ProHand SDK Demo: show every value the SDK exposes.

A read-only dashboard. It sends no commands and never moves the hand, so it is
safe to leave running next to anything else — the one exception is `--ping`,
which sends a heartbeat so the status stream has traffic on an otherwise idle
driver.

Covers, in one place:

  * library version and USB discovery
  * connection liveness
  * `system_status()` — the aggregate roll-up, field by field
  * `thermal_load()` — per-subsystem thermal rates
  * `signal_rates()` — every alerting signature, thermal or not
  * `drain_events()` — qualified monitoring events
  * `try_recv_message()` — every decoded status frame kind

The status stream is unfiltered, so the frames below are exactly what the driver
published. Events are the *qualified* view alongside it: a single noisy sample
shows up as a frame and a low rate, but never as an event.
"""

import argparse
import sys
import time
from dataclasses import fields

from .utils import DemoBase

#: Hand-state codes, from the table in prohand_sdk.h.
HAND_STATES = {
    -1: "unknown (none reported yet)",
    0: "idle",
    1: "sleep",
    2: "ready",
    3: "running",
    4: "servicing",
    5: "calibrating",
    6: "error",
    7: "homing",
    8: "thermal protection",
}

HANDEDNESS = {0: "unknown", 1: "left", 2: "right"}
SEVERITY = {0: "info", 1: "warning", 2: "error"}

#: AlertSource is a bitflag; these are the individual bits.
ALERT_SOURCES = {
    1 << 0: "hand",
    1 << 1: "rotary",
    1 << 2: "linear",
    1 << 3: "calibration",
    1 << 4: "imu",
    1 << 5: "system",
}


def source_name(value: int) -> str:
    return ALERT_SOURCES.get(value, f"0x{value:02x}")


def actuator_name(value: int) -> str:
    """0xFF is the wire's marker for 'not actuator-specific'."""
    return "n/a" if value == 0xFF else str(value)


def brief(values, limit: int = 8, fmt: str = "{}") -> str:
    """First few entries of a long array, so a 16-actuator row stays readable."""
    shown = ", ".join(fmt.format(v) for v in list(values)[:limit])
    more = len(values) - limit
    return f"[{shown}{f', +{more} more' if more > 0 else ''}]"


class ShowAllDemo(DemoBase):
    """Print every value the SDK exposes, refreshing on an interval."""

    def __init__(self):
        super().__init__("ProHand SDK — every value")
        # Latest frame of each kind, so a slow-moving frame (handedness, state)
        # stays on screen instead of flickering away between refreshes.
        self.latest = {}
        self.frame_counts = {}

    # ── static, printed once ────────────────────────────────────────────────

    def show_library(self):
        self.section("Library")
        print(f"  SDK version:        {self.sdk.get_version()}")
        print(f"  Message kinds:      {len(list(self.sdk.MessageKind))}")
        print(f"  Event kinds:        {[k.name for k in self.sdk.SystemEventKind]}")

        devices = self.sdk.discover_usb_devices()
        print(f"  USB devices:        {len(devices)}")
        for d in devices:
            print(f"    - {d.display_name}  ({d.port_name})")

    # ── refreshed each tick ─────────────────────────────────────────────────

    def show_system_status(self, client):
        """The aggregate roll-up — the call most consumers should reach for."""
        self.section("System status")
        s = client.system_status()

        heartbeat = (
            "never"
            if s.ms_since_heartbeat == 2**64 - 1
            else f"{s.ms_since_heartbeat} ms ago"
        )
        print(f"  connected:              {s.connected}")
        print(f"  last status:            {heartbeat}")
        print(
            f"  hand_state:             {s.hand_state} ({HAND_STATES.get(s.hand_state, '?')})"
        )
        print(f"  handedness:             {HANDEDNESS.get(s.handedness, '?')}")
        print(f"  thermal_lockdown:       {s.thermal_lockdown}")
        print(f"  worst_warning_percent:  {s.worst_warning_percent}%")
        print(f"  worst_lockdown_percent: {s.worst_lockdown_percent}%")
        print(f"  worst_actuator:         {actuator_name(s.worst_actuator)}")
        print(f"  peak_temp_c:            {s.peak_temp_c} C")
        print(f"  active_signals:         {s.active_signals}")
        print(f"  alerts_in_window:       {s.alerts_in_window}")
        print(f"  worst_severity:         {SEVERITY.get(s.worst_severity, '?')}")

    def show_thermal(self, client):
        self.section("Thermal load (% of the maximum publishable alert rate)")
        loads = client.thermal_load()
        if not loads:
            print("  nothing warm — no subsystem has alerted inside the window")
            return
        print(
            f"  {'source':<8} {'act':>4} {'warn':>6} {'lock':>6} {'last':>6} {'peak':>6}"
        )
        for load in loads:
            print(
                f"  {source_name(load.source):<8} {actuator_name(load.actuator):>4} "
                f"{load.warning_percent:>5}% {load.lockdown_percent:>5}% "
                f"{load.last_temp_c:>5}C {load.peak_temp_c:>5}C"
            )
        worst = client.worst_thermal_load()
        if worst:
            print(
                f"  worst: {source_name(worst.source)} actuator "
                f"{actuator_name(worst.actuator)} at {worst.warning_percent}% warning"
            )

    def show_signal_rates(self, client):
        """Every alerting signature, not just thermal ones."""
        self.section("Signal rates (per unique source/severity/actuator/code)")
        rates = client.signal_rates()
        if not rates:
            print("  no signal has alerted inside the window")
            return
        print(f"  {'source':<8} {'sev':<8} {'act':>4} {'code':>5} {'rate':>6} {'n':>4}")
        for r in rates:
            print(
                f"  {source_name(r.source):<8} {SEVERITY.get(r.severity, '?'):<8} "
                f"{actuator_name(r.actuator):>4} {r.code:>5} "
                f"{r.rate_percent:>5}% {r.count_in_window:>4}"
            )

    def show_events(self, client):
        """Qualified events — a noisy sample never produces one."""
        self.section("Monitoring events")
        events = client.drain_events()
        dropped = client.dropped_events
        if not events:
            print(f"  none queued  (dropped since connect: {dropped})")
            return
        for e in events:
            print(
                f"  [{e.timestamp_ms:>8} ms] {e.kind.name:<24} "
                f"{source_name(e.source)} actuator {actuator_name(e.actuator)} "
                f"detail={e.detail} rate={e.rate_percent}%"
            )
        if dropped:
            self.warning(f"{dropped} events dropped — poll more often")

    def collect_frames(self, client, budget: int):
        """Drain the status stream, keeping the newest frame of each kind."""
        for _ in range(budget):
            frame = client.try_recv_message()
            if frame is None:
                break
            name = type(frame).__name__
            self.latest[name] = frame
            self.frame_counts[name] = self.frame_counts.get(name, 0) + 1

    def show_frames(self):
        self.section("Latest status frame of each kind")
        if not self.latest:
            print("  no status messages yet — is the driver running?")
            return

        for name, frame in sorted(self.latest.items()):
            count = self.frame_counts[name]
            print(f"  {name}  (seen {count}x)")
            for f in fields(frame):
                value = getattr(frame, f.name)
                if isinstance(value, (list, tuple)):
                    value = brief(value)
                elif f.name == "source":
                    value = source_name(int(value))
                elif f.name in ("severity", "thermal_event", "kind", "handedness"):
                    value = getattr(value, "name", value)
                print(f"      {f.name:<22} {value}")

    # ── entry point ─────────────────────────────────────────────────────────

    def run(self, args) -> int:
        self.banner()
        print(f"\nCommand endpoint:         {args.command_endpoint}")
        print(f"Status endpoint:          {args.status_endpoint}")

        self.show_library()

        try:
            self.section("Connecting")
            client = self.sdk.ProHandClient(
                args.command_endpoint,
                args.status_endpoint,
                args.hand_streaming_endpoint,
                args.wrist_streaming_endpoint,
            )
            self.success("connected" if client.is_connected() else "client created")

            tick = 0
            while args.count <= 0 or tick < args.count:
                tick += 1
                # A ping keeps traffic flowing on an otherwise idle driver, so
                # the heartbeat and frame table are not permanently empty.
                if args.ping:
                    client.send_ping()

                time.sleep(args.interval)
                self.collect_frames(client, args.drain)

                print("\n" + "=" * 68)
                print(f"tick {tick}   ({time.strftime('%H:%M:%S')})")
                print("=" * 68)
                self.show_system_status(client)
                self.show_thermal(client)
                self.show_signal_rates(client)
                self.show_events(client)
                self.show_frames()

            client.close()
            return 0

        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 0
        except Exception as e:  # noqa: BLE001 - a demo should report, not traceback
            self.error(f"{type(e).__name__}: {e}")
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show every value the ProHand SDK exposes.",
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
        "--count",
        type=int,
        default=0,
        help="refreshes before exiting (0 = until Ctrl-C)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="seconds between refreshes"
    )
    parser.add_argument(
        "--drain", type=int, default=500, help="max status messages to read per refresh"
    )
    parser.add_argument(
        "--ping",
        action="store_true",
        help="send a ping each refresh so an idle driver still produces traffic",
    )
    return ShowAllDemo().run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
