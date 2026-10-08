#!/usr/bin/env python3
"""
ProGlove SDK Demo: Connection Test

Tests basic connection to the ProGlove IPC host.
"""

import sys
import argparse
from .utils import DemoBase


class ConnectDemo(DemoBase):
    """Connection test demo."""

    def __init__(self):
        super().__init__("ProGlove IPC Connection Test")

    def run(self, connection_type: str, endpoint: str) -> int:
        """Run the connection test."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Mode:     {connection_type}")
        print(f"  Status endpoint: {endpoint}")

        try:
            self.section("Connecting to IPC host...")
            client = self.sdk.ProGloveClient(endpoint)

            # Wait for connection to establish (asynchronous background connection)
            self.info("Waiting for connection to establish...")
            import time

            max_wait = 2.0  # Maximum wait time in seconds
            poll_interval = 0.1  # Poll every 100ms
            start_time = time.time()

            while not client.is_connected() and (time.time() - start_time) < max_wait:
                time.sleep(poll_interval)

            if not client.is_connected():
                self.error("Failed to establish connection within timeout")
                self.info("Make sure the IPC host is running")
                client.close()
                return 1

            self.success("Successfully connected to IPC host")

            self.section("Testing communication...")
            client.send_ping()
            time.sleep(0.2)  # Wait for ping response
            self.success("Ping successful!")

            self.section("SDK Information:")
            print(f"  Version: {self.sdk.get_version()}")

            client.close()

            self.success("Connection test completed successfully!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure the ProGlove IPC host is running.")
            return 1
        except self.sdk.ProGloveError as e:
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
        description="Test connection to ProGlove IPC host",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect via IPC (local)
  python -m proglove_demo.connect --status-endpoint ipc:///tmp/proglove-left-status.ipc
  python -m proglove_demo.connect --status-endpoint ipc:///tmp/proglove-right-status.ipc

  # Connect via TCP (remote)
  python -m proglove_demo.connect --status-endpoint tcp://192.168.1.82:5566

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
    args = parser.parse_args()

    # Use the endpoint directly
    endpoint = args.status_endpoint
    connection_type = endpoint

    demo = ConnectDemo()
    return demo.run(connection_type, endpoint)


if __name__ == "__main__":
    sys.exit(main())
