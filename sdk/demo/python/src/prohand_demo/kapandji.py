#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Kapandji Opposition Test

Runs the Kapandji opposition sequence - thumb touches each fingertip.
"""

import sys
import argparse
import time
import math
from pathlib import Path
from typing import Dict, List, Optional
from .utils import DemoBase


def _safe_yaml_load(path: str) -> Optional[dict]:
    """Safely load YAML configuration file."""
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed; install it to use YAML gestures.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load YAML config from {path}: {e}")
        return None


def _parse_joint_list(
    values: Optional[List[float]], n: int, fill: float = 0.0
) -> List[float]:
    """Parse joint list from YAML, filling missing values."""
    if values is None:
        return [float(fill)] * n
    out = [float(v) for v in values][:n]
    if len(out) < n:
        out.extend([float(fill)] * (n - len(out)))
    return out


def _pose_from_yaml(gesture: str, hand: str, cfg: dict) -> Dict[str, List[float]]:
    """Extract pose from YAML configuration."""
    hands = (cfg or {}).get("hands", {})
    if not hands:
        raise ValueError("YAML config missing 'hands' section")
    g = hands.get(gesture)
    if g is None:
        available = ", ".join(sorted(hands.keys()))
        raise ValueError(f"YAML gesture '{gesture}' not found. Available: {available}")

    def deg_to_rad_list(values: List[float], n: int) -> List[float]:
        vals = _parse_joint_list(values, n, fill=0.0)
        return [math.radians(v) for v in vals]

    thumb = deg_to_rad_list(g.get("thumb", []), 4)
    index = deg_to_rad_list(g.get("index", []), 4)
    middle = deg_to_rad_list(g.get("middle", []), 4)
    ring = deg_to_rad_list(g.get("ring", []), 4)
    pinky = deg_to_rad_list(g.get("pinky", []), 4)
    wrist = deg_to_rad_list(g.get("wrist", []), 2) if "wrist" in g else [0.0, 0.0]
    return {
        "thumb": thumb,
        "index": index,
        "middle": middle,
        "ring": ring,
        "pinky": pinky,
        "wrist": wrist,
    }


def _pose_to_hand_positions(pose: Dict[str, List[float]]) -> List[float]:
    """Convert pose dictionary to flat list of 20 joint positions."""
    # Order: thumb[0-3], index[4-7], middle[8-11], ring[12-15], pinky[16-19]
    positions = []
    positions.extend(pose["thumb"])
    positions.extend(pose["index"])
    positions.extend(pose["middle"])
    positions.extend(pose["ring"])
    positions.extend(pose["pinky"])
    return positions


def _stream_pose(
    client,
    pose: Dict[str, List[float]],
    publish_hz: float,
    duration_s: float,
    torque: float = 0.45,
) -> None:
    """Stream a pose for the specified duration."""
    period = 1.0 / max(1e-6, float(publish_hz))
    positions = _pose_to_hand_positions(pose)
    wrist_positions = pose.get("wrist", [0.0, 0.0])

    deadline = time.time() + float(duration_s)
    while time.time() < deadline:
        client.send_wrist_streams(wrist_positions)
        client.send_hand_streams(positions, torque)
        time.sleep(period)


class KapandjiDemo(DemoBase):
    """Kapandji opposition test demo."""

    def __init__(self):
        super().__init__("ProHand Kapandji Opposition Test")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        yaml_config: str,
        hand: str,
        publish_freq: float,
    ) -> int:
        """Run the Kapandji demo."""
        self.banner()

        print("\nConfiguration:")
        print(f"  YAML config:      {yaml_config}")
        print(f"  Hand:             {hand}")
        print(f"  Publish rate:     {publish_freq} Hz")

        client = None
        try:
            # Load YAML configuration
            self.section("Loading YAML configuration...")
            cfg = _safe_yaml_load(yaml_config)
            if cfg is None:
                self.error("YAML config required for Kapandji sequence")
                return 1
            self.success("YAML configuration loaded!")

            # Resolve torque level from YAML
            torque_level: float = 0.45
            try:
                level = (cfg or {}).get("default_torque_level")
                tmap = (cfg or {}).get("torque_map", {}) or {}
                if isinstance(level, str) and level in tmap:
                    torque_level = float(tmap[level])
            except Exception:
                torque_level = 0.45

            # Connect to IPC host
            self.section("Connecting to IPC host with streaming...")
            client = self.sdk.ProHandClient(
                command_endpoint,
                status_endpoint,
                hand_streaming_endpoint,
                wrist_streaming_endpoint,
            )
            self.success("Connected with streaming support!")

            # Verify connection
            self.section("Verifying connection...")
            client.send_ping()
            time.sleep(0.2)
            self.success("Connection verified!")

            # Enable streaming mode
            self.section("Enabling streaming mode...")
            client.set_streaming_mode(True)
            if not client.wait_for_streaming_ready(timeout=10.0):
                self.error("Streaming connection failed to establish!")
                return 1
            self.success("Streaming mode enabled!")

            # Run Kapandji sequence
            self.section("Running Kapandji opposition sequence...")
            sequence: List[tuple[str, float]] = [
                # Slow
                ("finger_down_0", 2.0),
                ("finger_down_1", 1.0),
                ("finger_down_2", 1.0),
                ("finger_down_3", 1.0),
                ("finger_down_4", 1.0),
                ("finger_down_3", 1.0),
                ("finger_down_2", 1.0),
                ("finger_down_1", 1.0),
                # Medium
                ("finger_down_0", 1.25),
                ("finger_down_1", 0.5),
                ("finger_down_2", 0.5),
                ("finger_down_3", 0.5),
                ("finger_down_4", 0.5),
                ("finger_down_3", 0.5),
                ("finger_down_2", 0.5),
                ("finger_down_1", 0.5),
                # Fast
                ("finger_down_0", 0.5),
                ("finger_down_1", 0.25),
                ("finger_down_2", 0.25),
                ("finger_down_3", 0.25),
                ("finger_down_4", 0.25),
                ("finger_down_3", 0.25),
                ("finger_down_2", 0.25),
                ("finger_down_1", 0.25),
                # Fastest
                ("finger_down_0", 0.25),
                ("finger_down_1", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_4", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_1", 0.1),
                # Fastest (repeat)
                ("finger_down_0", 0.25),
                ("finger_down_1", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_4", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_1", 0.1),
                # Fastest (repeat)
                ("finger_down_0", 0.25),
                ("finger_down_1", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_4", 0.1),
                ("finger_down_3", 0.1),
                ("finger_down_2", 0.1),
                ("finger_down_1", 0.1),
            ]

            for gesture, dur in sequence:
                pose = _pose_from_yaml(gesture, hand, cfg)
                print(f"  Gesture: {gesture} for {dur:.2f}s")
                _stream_pose(client, pose, publish_freq, dur, torque_level)

            # Return to zero
            self.section("Returning to zero position...")
            zero_positions = [0.0] * 20
            client.send_hand_streams(zero_positions, torque_level)
            client.send_wrist_streams([0.0, 0.0])
            time.sleep(0.5)

            # Disable streaming mode
            self.section("Disabling streaming mode...")
            client.set_streaming_mode(False)
            time.sleep(0.2)

            self.success("Kapandji sequence completed!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prohand-headless-ipc-host is running")
            return 1
        except self.sdk.ProHandError as e:
            self.error(f"Kapandji test failed: {e}")
            return 1
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return 1
        finally:
            if client is not None:
                try:
                    client.set_streaming_mode(False)
                except Exception:
                    pass
                try:
                    client.close()
                except Exception:
                    pass


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Kapandji opposition sequence (placeholder)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--command-endpoint",
        type=str,
        default="ipc:///tmp/prohand-commands.ipc",
        help="ZMQ command endpoint",
    )
    parser.add_argument(
        "--status-endpoint",
        type=str,
        default="ipc:///tmp/prohand-status.ipc",
        help="ZMQ status endpoint",
    )
    parser.add_argument(
        "--hand-streaming-endpoint",
        type=str,
        default="ipc:///tmp/prohand-hand-streaming.ipc",
        help="ZMQ hand streaming endpoint",
    )
    parser.add_argument(
        "--wrist-streaming-endpoint",
        type=str,
        default="ipc:///tmp/prohand-wrist-streaming.ipc",
        help="ZMQ wrist streaming endpoint",
    )
    # Default YAML path relative to this script's location
    script_dir = Path(__file__).parent
    default_yaml = script_dir / "../../../config/kapandji.yaml"
    default_yaml = default_yaml.resolve()

    parser.add_argument(
        "--yaml-config",
        type=str,
        default=str(default_yaml),
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--hand",
        type=str,
        default="left",
        choices=["left", "right"],
        help="Which hand configuration to use",
    )
    parser.add_argument(
        "--publish-frequency",
        type=float,
        default=60.0,
        help="Command publish rate (Hz)",
    )
    args = parser.parse_args()

    demo = KapandjiDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
        args.yaml_config,
        args.hand,
        args.publish_frequency,
    )


if __name__ == "__main__":
    sys.exit(main())
