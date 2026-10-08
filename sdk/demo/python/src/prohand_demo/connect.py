#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Connection Test

Tests basic connection to the ProHand IPC host.
"""

import sys
import argparse
from .utils import DemoBase


class ConnectDemo(DemoBase):
    """Connection test demo."""

    def __init__(self):
        super().__init__("ProHand IPC Connection Test")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
    ) -> int:
        """Run the connection test."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Command endpoint:       {command_endpoint}")
        print(f"  Status endpoint:         {status_endpoint}")
        print(f"  Hand streaming endpoint: {hand_streaming_endpoint}")
        print(f"  Wrist streaming endpoint: {wrist_streaming_endpoint}")

        try:
            self.section("Connecting to IPC host...")
            client = self.sdk.ProHandClient(
                command_endpoint,
                status_endpoint,
                hand_streaming_endpoint,
                wrist_streaming_endpoint,
            )

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
            print("\nMake sure the ProHand IPC host is running.")
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
        description="Test connection to ProHand IPC host",
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
    args = parser.parse_args()

    demo = ConnectDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
    )


if __name__ == "__main__":
    sys.exit(main())
