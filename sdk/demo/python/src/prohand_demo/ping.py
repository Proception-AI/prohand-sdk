#!/usr/bin/env python3
"""
ProHand SDK FFI Demo: Ping Command

Connects to the IPC host and sends periodic ping commands.
"""

import sys
import argparse
import time
from .utils import DemoBase


class PingDemo(DemoBase):
    """Ping command demo."""

    def __init__(self):
        super().__init__("ProHand Ping Demo")

    def run(
        self,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        count: int,
        interval: float,
    ) -> int:
        """Run the ping demo."""
        self.banner()
        print(f"\nCommand endpoint:       {command_endpoint}")
        print(f"Status endpoint:         {status_endpoint}")
        print(f"Hand streaming endpoint: {hand_streaming_endpoint}")
        print(f"Wrist streaming endpoint: {wrist_streaming_endpoint}")
        print(f"Ping count:              {count if count > 0 else 'infinite'}")
        print(f"Interval:                {interval}s")

        try:
            self.section("Connecting...")
            client = self.sdk.ProHandClient(
                command_endpoint,
                status_endpoint,
                hand_streaming_endpoint,
                wrist_streaming_endpoint,
            )
            self.success("Connected!\n")

            ping_count = 0
            start_time = time.time()

            try:
                while count == 0 or ping_count < count:
                    client.send_ping()
                    ping_count += 1
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:6.2f}s] Ping #{ping_count} sent ✓")

                    if count > 0 and ping_count >= count:
                        break

                    time.sleep(interval)

            except KeyboardInterrupt:
                print("\n")
                self.info("Interrupted by user")
            finally:
                client.close()

            self.success(f"Sent {ping_count} ping(s) successfully")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prohand-headless-ipc-host is running")
            return 1
        except self.sdk.ProHandError as e:
            self.error(f"Command failed: {e}")
            return 1
        except Exception as e:
            self.error(f"Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Send ping commands to ProHand IPC host",
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
        "--count", type=int, default=10, help="Number of pings to send (0 = infinite)"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Interval between pings (seconds)"
    )
    args = parser.parse_args()

    demo = PingDemo()
    return demo.run(
        args.command_endpoint,
        args.status_endpoint,
        args.hand_streaming_endpoint,
        args.wrist_streaming_endpoint,
        args.count,
        args.interval,
    )


if __name__ == "__main__":
    sys.exit(main())
