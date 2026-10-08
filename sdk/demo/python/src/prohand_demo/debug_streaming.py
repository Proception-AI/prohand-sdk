#!/usr/bin/env python3
"""
ProHand SDK FFI Debug: Streaming Mode Verification

Debug tool to verify streaming mode is properly received by the driver.
"""

import sys
import argparse
import time
from .utils import DemoBase


class DebugStreamingDemo(DemoBase):
    """Debug streaming mode connectivity."""

    def __init__(self):
        super().__init__("ProHand Debug: Streaming Mode Verification")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        test_commands: bool,
    ) -> int:
        """Run the streaming debug demo."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Command endpoint:       {command_endpoint}")
        print(f"  Status endpoint:         {status_endpoint}")
        print(f"  Hand streaming endpoint: {hand_streaming_endpoint}")
        print(f"  Wrist streaming endpoint: {wrist_streaming_endpoint}")
        print(f"  Test commands:          {test_commands}")

        try:
            # Step 1: Create client
            self.section("Step 1: Creating client with streaming...")
            client = self.sdk.ProHandClient(
                command_endpoint,
                status_endpoint,
                hand_streaming_endpoint,
                wrist_streaming_endpoint,
            )
            self.success("Client created with streaming support!")
            print(f"  Connected: {client.is_connected()}")

            # Step 2: Wait for ZMQ to establish
            self.section("Step 2: Waiting for ZMQ connection...")
            time.sleep(1.0)
            print(f"  Connected: {client.is_connected()}")

            # Step 3: Send initial ping
            self.section("Step 3: Sending initial ping...")
            try:
                client.send_ping()
                self.success("Ping sent successfully!")
            except Exception as e:
                self.error(f"Ping failed: {e}")
                return 1

            # Step 4: Wait for ping response
            time.sleep(0.2)
            print(f"  Connected: {client.is_connected()}")

            # Step 5: Enable streaming mode on driver
            self.section("Step 5: Enabling streaming mode on driver...")
            print(
                "  Note: Having 3 endpoints is not enough - driver must be "
                "told to enable streaming"
            )
            try:
                client.set_streaming_mode(True)
                self.success("set_streaming_mode(True) sent successfully!")
            except Exception as e:
                self.error(f"set_streaming_mode failed: {e}")
                return 1

            # Step 6: Wait for ZMQ streaming connection (slow joiner problem)
            self.section("Step 6: Waiting for ZMQ streaming socket to connect...")
            print("  Note: ZMQ PUB/SUB sockets need ~100-200ms to establish connection")
            print("  This is the 'slow joiner' problem in ZMQ")
            print("  Using wait_for_streaming_ready() to verify connection...")
            print("  Note: Driver must be connected to device and in Running state")

            if not client.wait_for_streaming_ready(timeout=5.0):
                self.error("Streaming connection failed to establish within timeout!")
                self.info("This may happen if:")
                self.info("  1. Device is not connected to the driver")
                self.info("  2. Device is not in Running state")
                self.info("  3. Driver is not sending status messages")
                self.info("  4. Check driver logs for errors")
                return 1

            self.success("ZMQ connection verified and ready!")

            # Step 7: Verify with another ping
            self.section("Step 7: Verifying connection...")
            try:
                client.send_ping()
                self.success("Verification ping sent!")
            except Exception as e:
                self.error(f"Verification ping failed: {e}")
                return 1

            time.sleep(0.2)

            # Step 8: Test sending commands if requested
            if test_commands:
                self.section("Step 8: Testing rotary commands...")
                try:
                    positions = [0.0] * 16
                    torques = [0.45] * 16

                    for i in range(5):
                        client.send_rotary_streams(positions, torques)
                        print(f"  Command {i + 1}/5 sent via streaming")
                        time.sleep(0.01)  # 100Hz

                    self.success("Test commands sent successfully!")
                except Exception as e:
                    self.error(f"Command sending failed: {e}")
                    return 1

            # Step 9: Disable streaming mode
            self.section("Step 9: Disabling streaming mode...")
            try:
                client.set_streaming_mode(False)
                self.success("Streaming mode disabled!")
            except Exception as e:
                self.error(f"Disabling streaming failed: {e}")

            time.sleep(0.2)

            # Step 10: Clean up
            self.section("Step 10: Cleaning up...")
            client.close()
            self.success("Client closed!")

            print("\n" + "=" * 60)
            self.success("Debug session completed!")
            print("\nHow 4-endpoint streaming works:")
            print(
                "  1. Create client with 4 endpoints (command, status, "
                "hand_streaming, wrist_streaming)"
            )
            print("  2. Send set_streaming_mode(True) via COMMAND socket")
            print(
                "  3. Driver enables streaming and listens on HAND and "
                "WRIST streaming sockets"
            )
            print(
                "  4. Hand commands use HAND socket, wrist commands use "
                "WRIST streaming socket"
            )
            print("  5. Other commands (ping, calibration) still use COMMAND socket")
            print("\nIf commands aren't working:")
            print("  1. Check driver logs for 'SetStreamingMode' command")
            print("  2. Verify all 4 ZMQ endpoints match between client and driver")
            print("  3. Ensure driver's streaming servers are enabled")
            print("  4. Check driver logs for incoming streaming commands")
            print("  5. Try using TCP endpoints for easier debugging")
            print("=" * 60)

            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prohand-headless-ipc-host is running")
            return 1
        except self.sdk.ProHandError as e:
            self.error(f"SDK error: {e}")
            return 1
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Debug streaming mode connectivity",
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
        "--test-commands",
        action="store_true",
        help="Send test rotary commands after enabling streaming",
    )
    args = parser.parse_args()

    demo = DebugStreamingDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
        args.test_commands,
    )


if __name__ == "__main__":
    sys.exit(main())
