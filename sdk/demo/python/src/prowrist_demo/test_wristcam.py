#!/usr/bin/env python3
"""
ProWristCam SDK Demo: Wrist Camera Monitor

Continuously polls JPEG frames from a wrist camera and displays per-frame
statistics (frame rate, UID, timestamp, JPEG size).  Optionally saves
the most-recent frame to disk on each refresh.
"""

import sys
import argparse
import os
import time
from .utils import DemoBase


class TestWristCamDemo(DemoBase):
    """Wrist camera frame monitor."""

    def __init__(self):
        super().__init__("ProWristCam SDK - Frame Monitor")

    def display_status(
        self,
        fps: float,
        frame_count: int,
        uid: int,
        timestamp: int,
        jpeg_size: int,
        save_path: str,
    ):
        """Render the live status panel."""
        self.banner()
        print()
        print(f"  Frames received : {frame_count:,}")
        print(f"  Frame rate      : {fps:.1f} fps")
        print()
        print(f"  Last frame UID  : {uid}")
        print(f"  Last timestamp  : {timestamp} ms")
        print(f"  Last JPEG size  : {jpeg_size:,} bytes")
        if save_path:
            print(f"  Saved to        : {save_path}")
        print()
        print("Press Ctrl+C to stop")

    def run(
        self,
        endpoint: str,
        duration: float,
        refresh_rate: float,
        save_dir: str,
    ) -> int:
        """Run the wrist camera monitor."""
        self.banner()

        print("\nConnection parameters:")
        print(f"  Endpoint:  {endpoint}")
        print(f"  Version:   {self.sdk.get_version()}")
        print("\nDisplay parameters:")
        print(f"  Duration:     {duration}s (0 = infinite)")
        print(f"  Refresh rate: {refresh_rate} Hz")
        if save_dir:
            print(f"  Save dir:     {save_dir}")
            os.makedirs(save_dir, exist_ok=True)

        client = None
        try:
            self.section(f"Connecting to {endpoint}...")
            client = self.sdk.WristCamClient(endpoint)
            self.success("Client created!")

            self.section("Waiting for first frame...")
            deadline = time.time() + 10.0
            while time.time() < deadline:
                frame = client.try_recv_frame()
                if frame:
                    self.success("Stream is live!")
                    break
                time.sleep(0.01)
            else:
                self.warning("No frames within 10 s — continuing anyway")

            self.section("Monitoring wrist camera stream...")
            time.sleep(0.3)

            start_time = time.time()
            last_display = start_time
            display_interval = 1.0 / max(refresh_rate, 0.1)

            fps_start = start_time
            fps_count = 0
            current_fps = 0.0

            last_uid = 0
            last_ts = 0
            last_size = 0
            total_frames = 0
            save_path_shown = ""

            while True:
                elapsed = time.time() - start_time
                if duration > 0 and elapsed >= duration:
                    break

                frame = client.try_recv_frame()
                if frame:
                    fps_count += 1
                    total_frames += 1
                    last_uid = frame.uid
                    last_ts = frame.timestamp
                    last_size = len(frame.jpeg)

                    # Optionally persist the latest JPEG
                    if save_dir and frame.jpeg:
                        save_path = os.path.join(save_dir, f"frame_{frame.uid:05d}.jpg")
                        with open(save_path, "wb") as fh:
                            fh.write(frame.jpeg)
                        save_path_shown = save_path

                # Update FPS counter
                fps_elapsed = time.time() - fps_start
                if fps_elapsed >= 1.0:
                    current_fps = fps_count / fps_elapsed
                    fps_count = 0
                    fps_start = time.time()

                # Refresh display
                now = time.time()
                if now - last_display >= display_interval:
                    self.display_status(
                        current_fps,
                        total_frames,
                        last_uid,
                        last_ts,
                        last_size,
                        save_path_shown,
                    )
                    last_display = now
                    save_path_shown = ""

                time.sleep(0.0001)

            self.success(f"Monitoring complete — {total_frames} frames received")
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
        description="Monitor JPEG frames from a wrist camera",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor left camera via IPC
  python -m prowrist_demo.test_wristcam --endpoint ipc:///tmp/prowristcam-left-stream.ipc

  # Monitor right camera via TCP, save every frame
  python -m prowrist_demo.test_wristcam \\
      --endpoint tcp://192.168.1.82:5575 \\
      --save-dir /tmp/frames

  # Run for 10 s at 5 Hz display refresh
  python -m prowrist_demo.test_wristcam \\
      --endpoint tcp://127.0.0.1:5565 \\
      --duration 10 --refresh-rate 5

Default TCP ports:
  Left  wrist: tcp://127.0.0.1:5565
  Right wrist: tcp://127.0.0.1:5575
""",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="ipc:///tmp/prowristcam-left-stream.ipc",
        help="ZeroMQ stream endpoint (default: ipc:///tmp/prowristcam-left-stream.ipc)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Duration in seconds (0 = infinite, default: 0)",
    )
    parser.add_argument(
        "--refresh-rate",
        type=float,
        default=10.0,
        help="Terminal refresh rate in Hz (default: 10.0)",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="",
        help="Directory to save received JPEG frames (default: disabled)",
    )
    args = parser.parse_args()
    return TestWristCamDemo().run(
        args.endpoint,
        args.duration,
        args.refresh_rate,
        args.save_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
