#!/usr/bin/env python3
"""
ProGlove SDK Demo: Test Glove - Tactile Sensor Monitor

Reads all taxel data from the glove and displays it in the terminal.
Taxel data is organized by joint segment (DIP/MCP/PIP per finger).
"""

import sys
import argparse
import time
from .utils import DemoBase


class TestGloveDemo(DemoBase):
    """Tactile sensor monitoring demo."""

    def __init__(self):
        super().__init__("ProGlove Test Glove - Tactile Sensor Monitor")

    def display_status(self, status, rate: float):
        """Display tactile status in a formatted way."""
        # Clear previous output (move cursor up and clear lines)
        # Using ANSI escape codes for terminal control
        self.banner()
        print()
        print(
            f"Timestamp: {status.timestamp:5d} | UID: {status.uid} | "
            f"Rate: {rate:.1f} Hz"
        )
        print()

        # Thumb (largest finger)
        print(f"THUMB:  DIP[{len(status.t_dip):2d}]: {status.t_dip}")
        print(f"        PIP[{len(status.t_pip):2d}]: {status.t_pip}")
        print(f"        MCP[{len(status.t_mcp):2d}]: {status.t_mcp}")

        # Index
        print(f"INDEX:  DIP[{len(status.i_dip):2d}]: {status.i_dip}")
        print(f"        PIP[{len(status.i_pip):2d}]: {status.i_pip}")
        print(f"        MCP[{len(status.i_mcp):2d}]: {status.i_mcp}")

        # Middle
        print(f"MIDDLE: DIP[{len(status.m_dip):2d}]: {status.m_dip}")
        print(f"        PIP[{len(status.m_pip):2d}]: {status.m_pip}")
        print(f"        MCP[{len(status.m_mcp):2d}]: {status.m_mcp}")

        # Ring
        print(f"RING:   DIP[{len(status.r_dip):2d}]: {status.r_dip}")
        print(f"        PIP[{len(status.r_pip):2d}]: {status.r_pip}")
        print(f"        MCP[{len(status.r_mcp):2d}]: {status.r_mcp}")

        # Pinky
        print(f"PINKY:  DIP[{len(status.p_dip):2d}]: {status.p_dip}")
        print(f"        PIP[{len(status.p_pip):2d}]: {status.p_pip}")
        print(f"        MCP[{len(status.p_mcp):2d}]: {status.p_mcp}")

        # Palm (show all 16 taxels per segment)
        print()
        print(f"PALM:   Upper [{len(status.upper_palm):2d}]: {status.upper_palm}")
        print(f"        Middle[{len(status.middle_palm):2d}]: {status.middle_palm}")
        print(f"        Lower [{len(status.lower_palm):2d}]: {status.lower_palm}")

        print()
        print("Press Ctrl+C to stop")

    def run(
        self,
        connection_type: str,
        endpoint: str,
        duration: float,
        refresh_rate: float,
    ) -> int:
        """Run the test glove demo."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Mode:     {connection_type}")
        print(f"  Status endpoint: {endpoint}")

        print("\nDisplay parameters:")
        print(f"  Duration:     {duration}s (0 = infinite)")
        print(f"  Refresh rate: {refresh_rate} Hz")

        client = None
        try:
            self.section(f"Connecting to {endpoint}...")
            client = self.sdk.ProGloveClient(endpoint)
            self.success("Client created!")

            # Verify connection by waiting for data
            self.section("Verifying connection...")
            client.send_ping()
            self.success("Connection verified!")

            # Monitoring loop
            self.section("Starting tactile sensor monitoring...")
            time.sleep(0.5)

            start_time = time.time()
            last_display_time = start_time
            display_interval = 1.0 / refresh_rate

            rate_start_time = start_time
            rate_samples = 0
            current_rate = 0.0

            while True:
                # Check duration limit
                elapsed = time.time() - start_time
                if duration > 0 and elapsed >= duration:
                    break

                # Poll for status updates
                status = client.try_recv_status()
                if status and status.is_valid:
                    rate_samples += 1

                    # Update rate calculation every second
                    rate_elapsed = time.time() - rate_start_time
                    if rate_elapsed >= 1.0:
                        current_rate = rate_samples / rate_elapsed
                        rate_samples = 0
                        rate_start_time = time.time()

                    # Display at configured refresh rate
                    now = time.time()
                    if now - last_display_time >= display_interval:
                        self.display_status(status, current_rate)
                        last_display_time = now

                # Small sleep to avoid busy-waiting
                time.sleep(0.0001)

            self.success("Monitoring completed!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure proglove-headless-ipc-host is running")
            return 1
        except self.sdk.ProGloveError as e:
            self.error(f"Demo failed: {e}")
            return 1
        except KeyboardInterrupt:
            self.info("\nInterrupted by user")
            return 0
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return 1
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor tactile sensor data from ProGlove",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect via IPC (local)
  python -m proglove_demo.test_glove --status-endpoint ipc:///tmp/proglove-left-status.ipc
  python -m proglove_demo.test_glove --status-endpoint ipc:///tmp/proglove-right-status.ipc

  # Connect via TCP (remote)
  python -m proglove_demo.test_glove --status-endpoint tcp://192.168.1.82:5566
  python -m proglove_demo.test_glove --status-endpoint tcp://127.0.0.1:5566

Default endpoints:
  Left hand (IPC):  ipc:///tmp/proglove-left-status.ipc
  Right hand (IPC): ipc:///tmp/proglove-right-status.ipc
  Left hand (TCP):  tcp://127.0.0.1:5566
  Right hand (TCP): tcp://127.0.0.1:5576
""",
    )
    parser.add_argument(
        "--status-endpoint",
        type=str,
        required=True,
        help="ZeroMQ status endpoint (e.g., tcp://192.168.1.82:5566 or ipc:///tmp/proglove-left-status.ipc)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Duration to run in seconds (0 = infinite, default: 0)",
    )
    parser.add_argument(
        "--refresh-rate",
        type=float,
        default=10.0,
        help="Terminal refresh rate in Hz (default: 10.0)",
    )
    args = parser.parse_args()

    # Use the endpoint directly
    endpoint = args.status_endpoint
    connection_type = endpoint

    demo = TestGloveDemo()
    return demo.run(
        connection_type,
        endpoint,
        args.duration,
        args.refresh_rate,
    )


if __name__ == "__main__":
    sys.exit(main())
