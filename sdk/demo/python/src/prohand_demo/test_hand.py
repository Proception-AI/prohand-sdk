#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Test Hand - Individual Joint Testing

Tests each joint of each finger individually with cyclic motion.
"""

import sys
import argparse
import time
from .utils import DemoBase


class TestHandDemo(DemoBase):
    """Individual joint testing demo."""

    def __init__(self):
        super().__init__("ProHand Test Hand - Individual Joint Testing")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        delay: float,
        cycles: int,
    ) -> int:
        """Run the test hand demo."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Command endpoint:       {command_endpoint}")
        print(f"  Status endpoint:         {status_endpoint}")
        print(f"  Hand streaming endpoint: {hand_streaming_endpoint}")
        print(f"  Wrist streaming endpoint: {wrist_streaming_endpoint}")

        print("\nTest parameters:")
        print(f"  Delay between moves: {delay}s")
        print(f"  Cycles per joint:    {cycles}")

        client = None
        try:
            self.section("Connecting to IPC host with streaming...")
            client = self.sdk.ProHandClient(
                command_endpoint,
                status_endpoint,
                hand_streaming_endpoint,
                wrist_streaming_endpoint,
            )
            self.success("Connected with streaming support!")

            # Verify connection with a ping
            self.section("Verifying connection...")
            client.send_ping()
            time.sleep(0.2)  # Wait for ping response
            self.success("Connection verified!")

            # Enable streaming mode on the driver
            self.section("Enabling streaming mode...")
            self.info("Telling driver to accept streaming commands...")
            client.set_streaming_mode(True)

            # Wait for streaming connection to be established (with verification)
            self.info("Waiting for streaming connection to be ready...")
            if not client.wait_for_streaming_ready(timeout=5.0):
                self.error("Streaming connection failed to establish!")
                self.info(
                    "This may happen if the driver is busy, device is not "
                    "connected, or not in Running state."
                )
                return 1

            self.success("Streaming mode enabled! Commands will use streaming socket.")

            fingers = ["thumb", "index", "middle", "ring", "pinky"]
            joint_names = ["metacarpal", "proximal", "intermediate", "distal"]

            # Zero all fingers initially (use streaming mode)
            self.section("Zeroing all fingers...")
            zero_positions = [0.0] * 20  # 5 fingers × 4 joints
            zero_wrist_positions = [0.0, 0.0]  # 2 wrist joints
            client.send_hand_streams(zero_positions, 0.45)
            client.send_wrist_streams(zero_wrist_positions)
            time.sleep(1.0)

            # Test each joint of each finger
            # Layout: thumb[0-3], index[4-7], middle[8-11], ring[12-15],
            # pinky[16-19]
            for finger_idx, finger in enumerate(fingers):
                for j in range(4):
                    joint_idx = finger_idx * 4 + j
                    self.section(f"{finger} - {joint_names[j]} (joint {joint_idx})")

                    # Determine range based on joint and finger
                    if j == 0 and finger != "thumb":
                        # Metacarpal (abduction)
                        min_deg, max_deg = -30.0, 30.0
                    else:
                        # Flexion joints
                        min_deg, max_deg = 0.0, 90.0

                    import math

                    min_rad = math.radians(min_deg)
                    max_rad = math.radians(max_deg)

                    # Run cycles (use streaming for high-frequency commands)
                    for cycle in range(cycles):
                        # Start with all zero (20 positions: 5 fingers × 4 joints)
                        positions = [0.0] * 20

                        # For distal (j==3), pre-flex intermediate
                        if j == 3 and finger != "thumb":
                            positions[joint_idx - 1] = math.radians(90.0)

                        # Move to max position (use streaming for high-frequency control)
                        positions[joint_idx] = max_rad
                        client.send_hand_streams(positions, 0.45)
                        client.send_wrist_streams(zero_wrist_positions)
                        time.sleep(delay)

                        # Move to min position
                        positions[joint_idx] = min_rad
                        client.send_hand_streams(positions, 0.45)
                        client.send_wrist_streams(zero_wrist_positions)
                        time.sleep(delay)

            # Return to zero (use streaming mode)
            self.section("Returning to zero position...")
            client.send_hand_streams(zero_positions, 0.45)
            client.send_wrist_streams(zero_wrist_positions)
            time.sleep(0.5)

            # Disable streaming mode
            self.section("Disabling streaming mode...")
            client.set_streaming_mode(False)
            time.sleep(0.2)

            self.success("Test hand demo completed!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prohand-headless-ipc-host is running")
            return 1
        except self.sdk.ProHandError as e:
            self.error(f"Demo failed: {e}")
            return 1
        except KeyboardInterrupt:
            self.info("\nInterrupted by user")
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
        description="Test each joint of each finger individually",
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
    parser.add_argument(
        "--delay", type=float, default=0.2, help="Delay between movements (seconds)"
    )
    parser.add_argument(
        "--cycles", type=int, default=5, help="Number of cycles per joint"
    )
    args = parser.parse_args()

    demo = TestHandDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
        args.delay,
        args.cycles,
    )


if __name__ == "__main__":
    sys.exit(main())
