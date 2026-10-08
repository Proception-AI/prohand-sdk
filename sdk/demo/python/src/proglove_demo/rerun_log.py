#!/usr/bin/env python3
"""
ProGlove SDK Demo: Rerun logger for raw + processed tactile.

Subscribes to a glove status endpoint and, when the driver also publishes on
the derived `-raw.ipc` node, to the pre-filter raw stream too — then logs both
to Rerun (rerun.io), time-aligned, so you can scrub raw vs processed side by
side and sanity-check tactile data for training.

    proglove-rerun --endpoint ipc:///tmp/proglove-left-status.ipc

Requires `rerun-sdk` and `numpy` (declared under the demo's dependencies).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from .utils import DemoBase

# Flattened taxel layout (segment order) — matches the driver / GUI `flatten`:
# thumb (20), each finger DIP/MCP/PIP (8 per finger), palm (48) = 100 taxels.
SEGMENTS = [
    "t_dip",
    "t_mcp",
    "t_pip",
    "i_dip",
    "i_mcp",
    "i_pip",
    "m_dip",
    "m_mcp",
    "m_pip",
    "r_dip",
    "r_mcp",
    "r_pip",
    "p_dip",
    "p_mcp",
    "p_pip",
    "upper_palm",
    "middle_palm",
    "lower_palm",
]

# Anatomical regions over the flattened array, for per-region trend lines.
REGIONS = [
    ("thumb", 0, 20),
    ("index", 20, 28),
    ("middle", 28, 36),
    ("ring", 36, 44),
    ("pinky", 44, 52),
    ("palm", 52, 100),
]


def flatten(status) -> list:
    """Concatenate a TactileStatus's per-segment lists into flat[100]."""
    flat = []
    for seg in SEGMENTS:
        flat.extend(getattr(status, seg))
    return flat


def _hand_from_endpoint(endpoint: str) -> str:
    """`left`/`right` from a `proglove-<hand>-status.ipc` endpoint (default left)."""
    return "right" if "right" in endpoint else "left"


def _platform_dir() -> Optional[str]:
    """This host's published driver/<platform>/ directory name, or None."""
    machine = platform.machine()
    if platform.system() == "Darwin":
        return "macos-arm64"
    if platform.system() == "Linux":
        return "linux-arm64" if machine in ("aarch64", "arm64") else "linux-x64"
    return None


def _find_driver_bin() -> Optional[str]:
    """Locate the glove driver binary.

    Search order: $PROGLOVE_DRIVER_BIN, then the published SDK layout
    (driver/<platform>/), then the monorepo workspace target/ (dev builds).
    """
    name = "proglove-headless-ipc-host"
    env = os.environ.get("PROGLOVE_DRIVER_BIN")
    if env and Path(env).is_file():
        return env
    # rerun_log.py → proglove_demo → src → python → demo → sdk → <root>
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


class RerunLogDemo(DemoBase):
    """Log raw + processed glove tactile to Rerun."""

    def __init__(self):
        super().__init__("ProGlove → Rerun tactile logger")

    def _wait_connected(self, client, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if client.is_connected():
                return True
            time.sleep(0.1)
        return client.is_connected()

    def _ensure_driver(self, endpoint: str) -> Tuple[bool, Optional[str]]:
        """Launch the glove driver in a detached tmux session if not already up.

        Returns `(ok, session)`: `ok` is whether to keep waiting for a
        connection; `session` is the tmux session *we* started (to kill on
        exit) or `None` if we reused an existing one / couldn't launch.
        """
        if shutil.which("tmux") is None:
            self.error(
                "tmux not found — install tmux, or start the driver yourself and pass --no-launch"
            )
            return (False, None)
        hand = _hand_from_endpoint(endpoint)
        session = f"proglove-{hand}"
        if _tmux_has_session(session):
            self.info(f"reusing existing driver tmux session '{session}'")
            return (True, None)
        bin_path = _find_driver_bin()
        if bin_path is None:
            self.error(
                "driver binary not found. Expected driver/<platform>/proglove-headless-ipc-host "
                "in the SDK; set PROGLOVE_DRIVER_BIN to its path, or start the driver yourself "
                "and re-run with --no-launch."
            )
            return (False, None)
        # `read` keeps the pane open after the driver exits so a crash or
        # handedness-mismatch stays visible when attaching.
        cmd = (
            f"RUST_LOG=info {bin_path} --node {hand} --hand {hand} "
            f'--zmq-status-path {endpoint}; echo "[driver exited $?]"; read'
        )
        subprocess.run(["tmux", "new-session", "-d", "-s", session, cmd], check=True)
        self.info(
            f"launched driver in tmux session '{session}'  (attach: tmux attach -t {session})"
        )
        return (True, session)

    def run(
        self,
        endpoint: str,
        duration: float,
        spawn: bool,
        launch: bool,
        keep_driver: bool,
        save: Optional[str] = None,
    ) -> int:
        self.banner()

        try:
            import numpy as np
            import rerun as rr
        except ImportError as e:
            self.error(f"missing dependency: {e}")
            self.info("Install with: uv pip install rerun-sdk numpy")
            return 1

        # `rr.Scalar` was renamed `rr.Scalars` in newer Rerun — accept either.
        Scalar = getattr(rr, "Scalar", None) or rr.Scalars

        # `set_time_seconds` → `set_time(timestamp=)` in Rerun 0.23; support both.
        def set_wallclock(t: float) -> None:
            try:
                rr.set_time("wallclock", timestamp=t)
            except (AttributeError, TypeError):
                rr.set_time_seconds("wallclock", t)

        self.section(f"Connecting to {endpoint}")
        client = self.sdk.ProGloveClient(endpoint)

        # Give any already-running driver a moment before launching our own.
        launched_session: Optional[str] = None
        if not self._wait_connected(client, 2.0) and launch:
            ok, launched_session = self._ensure_driver(endpoint)
            if not ok:
                client.close()
                return 1
            self.info(
                "waiting for driver (USB detect + handedness validation, ~10s)..."
            )
            self._wait_connected(client, 15.0)

        def stop_driver() -> None:
            if launched_session and not keep_driver:
                self.info(f"stopping driver (tmux session '{launched_session}')")
                subprocess.run(
                    ["tmux", "kill-session", "-t", launched_session],
                    capture_output=True,
                )

        if not client.is_connected():
            self.error(
                "no connection — driver didn't come up"
                if launch
                else "no connection — start the driver, or drop --no-launch to auto-start it"
            )
            client.close()
            stop_driver()
            return 1
        self.success("connected")

        has_raw = client.has_raw_tactile()
        if has_raw:
            self.info("raw node subscribed (-raw.ipc) — logging raw + processed")
        else:
            self.warning(
                "no raw node for this endpoint — logging processed only "
                "(raw needs a local -status.ipc endpoint + a driver publishing it)"
            )

        # A `--save` path records to a native Rerun `.rrd` (reopen later with
        # `rerun <file>.rrd`); otherwise stream live to the viewer.
        rr.init("proglove_tactile", spawn=(spawn and not save))
        if save:
            rr.save(save)
            self.info(f"recording to {save}")

        # Spatial palm layout: taxel (x, y) in flat reading order, parsed from
        # the bundled SVG (source-of-truth geometry). Rerun 2D is y-down like the
        # SVG, so raw coords render upright. Falls back to a bar chart if absent.
        from . import taxel_layout

        try:
            positions = np.array(
                taxel_layout.flat_positions(_hand_from_endpoint(endpoint)),
                dtype=np.float32,
            )
            self.info(f"palm layout loaded ({positions.shape[0]} taxels)")
        except Exception as e:  # missing/parse-failed asset — degrade gracefully
            self.warning(f"palm layout unavailable ({e}); using bar chart")
            positions = None

        # Clean 3-pane layout: Processed | Raw palms on top, region peaks below.
        # Best-effort — older Rerun without the blueprint API keeps auto-layout.
        try:
            import rerun.blueprint as rrb

            rr.send_blueprint(
                rrb.Blueprint(
                    rrb.Vertical(
                        rrb.Horizontal(
                            rrb.Spatial2DView(
                                origin="/tactile/processed", name="Processed"
                            ),
                            rrb.Spatial2DView(origin="/tactile/raw", name="Raw"),
                        ),
                        rrb.TimeSeriesView(origin="/regions", name="Region peaks"),
                        row_shares=[3, 1],
                    ),
                    collapse_panels=True,
                )
            )
        except Exception as e:
            self.info(f"(default layout; blueprint unavailable: {e})")

        # Full-scale per stream (12-bit ADC), mirroring the GUI defaults.
        PROCESSED_MAX, RAW_MAX = 800.0, 4095.0

        def hot(vals_norm):
            """(N,) in 0..1 → (N,3) uint8 black→red→yellow→white ramp."""
            t = np.clip(vals_norm, 0.0, 1.0)
            rgb = np.stack(
                [
                    np.clip(t * 3, 0, 1),
                    np.clip(t * 3 - 1, 0, 1),
                    np.clip(t * 3 - 2, 0, 1),
                ],
                axis=1,
            )
            return (rgb * 255).astype(np.uint8)

        def log_frame(stream: str, status, cmax: float) -> None:
            flat = np.array(flatten(status), dtype=np.float32)
            if positions is not None:
                rr.log(
                    f"tactile/{stream}",
                    rr.Points2D(positions, colors=hot(flat / cmax), radii=3.2),
                )
            else:
                rr.log(f"tactile/{stream}", rr.BarChart(flat.astype(np.uint16)))
            for name, lo, hi in REGIONS:
                seg = flat[lo:hi]
                rr.log(
                    f"regions/{stream}/{name}",
                    Scalar(float(seg.max()) if seg.size else 0.0),
                )

        self.section("Logging — Ctrl+C to stop")
        frames = 0
        start = time.time()
        try:
            while duration <= 0 or time.time() - start < duration:
                got = False
                # Drain everything queued this tick so raw/processed stay current.
                while True:
                    processed = client.try_recv_status()
                    if processed is None:
                        break
                    if processed.is_valid:
                        set_wallclock(time.time())
                        log_frame("processed", processed, PROCESSED_MAX)
                        frames += 1
                        got = True
                while has_raw:
                    raw = client.try_recv_raw_tactile()
                    if raw is None:
                        break
                    if raw.is_valid:
                        set_wallclock(time.time())
                        log_frame("raw", raw, RAW_MAX)
                        got = True
                if not got:
                    time.sleep(0.002)
        except KeyboardInterrupt:
            pass
        finally:
            self.success(f"logged {frames} processed frames")
            client.close()
            stop_driver()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Log glove raw+processed tactile to Rerun"
    )
    parser.add_argument(
        "--endpoint",
        default="ipc:///tmp/proglove-left-status.ipc",
        help="glove status endpoint (raw node is derived: -status.ipc → -raw.ipc)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="seconds to log (0 = until Ctrl+C)",
    )
    parser.add_argument(
        "--no-spawn",
        action="store_true",
        help="don't auto-launch the Rerun viewer (log to the default sink instead)",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
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
    args = parser.parse_args()
    return RerunLogDemo().run(
        args.endpoint,
        args.duration,
        not args.no_spawn,
        not args.no_launch,
        args.keep_driver,
        args.save,
    )


if __name__ == "__main__":
    sys.exit(main())
