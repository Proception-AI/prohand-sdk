#!/usr/bin/env python3
"""
ProWristCam SDK Demo: Basic Connection Test

Connects to a prowristcam-headless-ipc-host endpoint, waits for the first
JPEG frame to confirm the link is live, and prints metadata.
"""

import sys
import argparse
import time
from .utils import DemoBase


class ConnectDemo(DemoBase):
    """Basic connection test."""

    def __init__(self):
        super().__init__("ProWristCam IPC Connection Test")

    def run(self, endpoint: str) -> int:
        """Run the connection test."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Endpoint: {endpoint}")
        print(f"  Version:  {self.sdk.get_version()}")

        client = None
        try:
            self.section(f"Connecting to {endpoint}...")
            client = self.sdk.WristCamClient(endpoint)
            self.success("Client created!")

            self.section("Waiting for first frame (up to 5 s)...")
            deadline = time.time() + 5.0
            frame = None
            while time.time() < deadline:
                frame = client.try_recv_frame()
                if frame:
                    break
                time.sleep(0.01)

            if frame:
                self.success("Frame received!")
                print("\nFrame details:")
                print(f"  uid:       {frame.uid}")
                print(f"  timestamp: {frame.timestamp}")
                print(f"  JPEG size: {len(frame.jpeg):,} bytes")
                print(f"  Connected: {client.is_connected()}")
            else:
                self.warning("No frame received within 5 s")
                print("Make sure prowristcam-headless-ipc-host is running")
                return 1

            self.success("Connection test completed!")
            return 0

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure prowristcam-headless-ipc-host is running")
            return 1
        except self.sdk.WristCamError as e:
            self.error(f"SDK error: {e}")
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
        description="Test connection to a prowristcam-headless-ipc-host endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # IPC (local)
  python -m prowrist_demo.connect --endpoint ipc:///tmp/prowristcam-left-stream.ipc
  python -m prowrist_demo.connect --endpoint ipc:///tmp/prowristcam-right-stream.ipc

  # TCP (remote)
  python -m prowrist_demo.connect --endpoint tcp://192.168.1.82:5565
  python -m prowrist_demo.connect --endpoint tcp://127.0.0.1:5565

Default ports:
  Left  (TCP): tcp://127.0.0.1:5565
  Right (TCP): tcp://127.0.0.1:5575
""",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="ipc:///tmp/prowristcam-left-stream.ipc",
        help="ZeroMQ stream endpoint (default: ipc:///tmp/prowristcam-left-stream.ipc)",
    )
    args = parser.parse_args()
    return ConnectDemo().run(args.endpoint)


if __name__ == "__main__":
    sys.exit(main())
