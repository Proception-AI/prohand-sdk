#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Cyclic Joint Motion

Runs sine wave motion patterns across finger joints.
"""

import sys
import argparse
import time
import math
from .utils import DemoBase


class CyclicMotionDemo(DemoBase):
    """Cyclic motion demo with sine wave patterns."""

    def __init__(self):
        super().__init__("ProHand Cyclic Joint Motion")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        amp_scale: float,
        frequency: float,
        duration: float,
        pub_hz: float,
        include_thumb: bool,
        exclude_wrist: bool,
    ) -> int:
        """Run the cyclic motion demo."""
        self.banner()

        # Abduction is always disabled
        include_abduction = False

        print("\nConnection parameters:")
        print(f"  Command endpoint:       {command_endpoint}")
        print(f"  Status endpoint:         {status_endpoint}")
        print(f"  Hand streaming endpoint: {hand_streaming_endpoint}")
        print(f"  Wrist streaming endpoint: {wrist_streaming_endpoint}")

        print("\nMotion parameters:")
        print(f"  Amplitude scale:    {amp_scale}")
        print(f"  Frequency:          {frequency} Hz")
        print(f"  Duration:           {duration}s")
        print(f"  Publish rate:       {pub_hz} Hz")
        print(f"  Include thumb:      {include_thumb}")
        print(f"  Exclude wrist:      {exclude_wrist}")

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
            if not client.wait_for_streaming_ready(timeout=10.0):
                self.error("Streaming connection failed to establish!")
                return 1

            self.success("Streaming mode enabled! Commands will use streaming socket.")

            self.section(f"Running cyclic motion for {duration}s...")

            period = 1.0 / max(pub_hz, 1e-6)
            start_time = time.time()
            iteration = 0

            # Phase offsets for each finger (wave motion across fingers)
            fingers = ["thumb", "index", "middle", "ring", "pinky"]
            finger_phases = {
                name: (i / len(fingers)) * 2 * math.pi for i, name in enumerate(fingers)
            }

            # Max angles per joint (in degrees)
            finger_max_deg = [
                90.0,
                90.0,
                90.0,
                90.0,
            ]  # metacarpal, proximal, intermediate, distal
            wrist_max_deg = [30.0, 65.0]  # wrist joint 1, wrist joint 2

            while True:
                # Calculate target time for this iteration (fixed timing, no drift)
                now = time.time()
                t = now - start_time

                if t >= duration:
                    break

                # Calculate joint angles (20 rotary joints: 5 fingers × 4)
                # Layout: thumb(0-3), index(4-7), middle(8-11), ring(12-15),
                # pinky(16-19)
                positions = []

                for finger_idx, finger_name in enumerate(fingers):
                    base_phase = finger_phases[finger_name]
                    finger_joints = []

                    for j in range(4):  # 4 joints per finger
                        # Skip metacarpal (j=0) for non-thumb if no abduction
                        if (
                            (not include_abduction)
                            and j == 0
                            and finger_name != "thumb"
                        ):
                            finger_joints.append(0.0)
                        else:
                            # Per-joint phase offset: j * 0.4 creates wave along finger
                            joint_phase = (
                                2 * math.pi * frequency * t + (j * 0.4) + base_phase
                            )
                            # Normalized sine [0, 1]
                            s01 = 0.5 + 0.5 * math.sin(joint_phase)
                            # Scale by max angle and amplitude scale
                            joint_angle_deg = s01 * (finger_max_deg[j] * amp_scale)
                            finger_joints.append(math.radians(joint_angle_deg))

                    # Zero thumb joints if not included
                    if (not include_thumb) and finger_name == "thumb":
                        finger_joints[1] = finger_joints[2] = finger_joints[3] = 0.0

                    positions.extend(finger_joints)

                # Torque (0.0-1.0 normalized, single value for all joints)
                torque = 1.0  # Match original torque_level=1.0

                # Send hand command (high-level joint angles, uses inverse kinematics)
                # Uses streaming for high-frequency control
                client.send_hand_streams(positions, torque)

                # Wrist command (high-level wrist joints) - alternates between joints
                if not exclude_wrist:
                    period_wrist = 1.0 / max(1e-6, float(frequency))
                    seg = int((t / period_wrist)) % 2
                    local = 2 * math.pi * ((t % period_wrist) / period_wrist)
                    if seg == 0:
                        # First wrist joint
                        wrist_angle_deg = math.sin(local) * (
                            wrist_max_deg[0] * amp_scale
                        )
                        wrist_positions = [math.radians(wrist_angle_deg), 0.0]
                    else:
                        # Second wrist joint
                        wrist_angle_deg = math.sin(local) * (
                            wrist_max_deg[1] * amp_scale
                        )
                        wrist_positions = [0.0, math.radians(wrist_angle_deg)]
                    client.send_wrist_streams(wrist_positions)
                else:
                    client.send_wrist_streams([0.0, 0.0])

                iteration += 1
                if iteration % int(pub_hz) == 0:  # Print every second
                    main_phase = 2.0 * math.pi * frequency * t
                    phase_deg = math.degrees(main_phase) % 360
                    print(f"  [{t:6.2f}s] Running... (phase: {phase_deg:.1f}°)")

                # Sleep until target time (compensates for command sending time)
                next_target = start_time + ((iteration + 1) * period)
                sleep_time = next_target - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # Return to zero (use streaming mode)
            self.section("Returning to zero...")
            zero_positions = [0.0] * 20
            client.send_hand_streams(zero_positions, 1.0)
            if not exclude_wrist:
                client.send_wrist_streams([0.0, 0.0])
            time.sleep(0.5)

            # Disable streaming mode
            self.section("Disabling streaming mode...")
            client.set_streaming_mode(False)
            time.sleep(0.2)

            self.success("Cyclic motion demo completed!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prohand-headless-ipc-host is running")
            return 1
        except self.sdk.ProHandError as e:
            self.error(f"Motion failed: {e}")
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
        description="Run cyclic joint motion patterns",
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
        "--amp-scale", type=float, default=0.8, help="Amplitude scale factor"
    )
    parser.add_argument(
        "--frequency", type=float, default=0.5, help="Motion frequency (Hz)"
    )
    parser.add_argument(
        "--duration", type=float, default=60.0, help="Duration (seconds)"
    )
    parser.add_argument(
        "--pub-hz", type=float, default=100.0, help="Command publish rate (Hz)"
    )
    parser.add_argument(
        "--include-thumb", action="store_true", help="Include thumb in motion"
    )
    parser.add_argument(
        "--exclude-wrist", action="store_true", help="Exclude wrist from motion"
    )
    args = parser.parse_args()

    demo = CyclicMotionDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
        args.amp_scale,
        args.frequency,
        args.duration,
        args.pub_hz,
        args.include_thumb,
        args.exclude_wrist,
    )


if __name__ == "__main__":
    sys.exit(main())
