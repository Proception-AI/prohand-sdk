#!/usr/bin/env python3
"""
ProGlove SDK Demo: OTA Firmware Update

Drives a firmware update over the OTA bulk interface: sends the image size
(+ ed25519 key/sig, currently unenforced firmware-side), then answers each
RequestPage(addr) from firmware with the 256-byte page at that address until
firmware replies Success (or Err).
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
from .utils import DemoBase

PAGE_SIZE = 256
KEY_SIZE = 32
SIG_SIZE = 64


class TestOtaDemo(DemoBase):
    """OTA firmware update demo."""

    def __init__(self):
        super().__init__("ProGlove OTA Firmware Update")

    def run(
        self,
        endpoint: str,
        image_path: str,
        key_path: Optional[str],
        sig_path: Optional[str],
        timeout: float,
    ) -> int:
        """Run the OTA demo."""
        self.banner()
        print(f"\nStatus endpoint: {endpoint}")
        print(f"Firmware image:  {image_path}")

        image = Path(image_path).read_bytes()
        size = len(image)
        print(
            f"Image size:      {size} bytes ({(size + PAGE_SIZE - 1) // PAGE_SIZE} pages)"
        )

        # Verification is currently unenforced firmware-side (see
        # fw/pro_hal/src/ota.rs) — zero-filled key/sig work today, but pass
        # --key-file/--sig-file if/when that changes.
        key = Path(key_path).read_bytes() if key_path else bytes(KEY_SIZE)
        sig = Path(sig_path).read_bytes() if sig_path else bytes(SIG_SIZE)
        if len(key) != KEY_SIZE:
            self.error(f"key must be {KEY_SIZE} bytes, got {len(key)}")
            return 1
        if len(sig) != SIG_SIZE:
            self.error(f"sig must be {SIG_SIZE} bytes, got {len(sig)}")
            return 1

        client = None
        try:
            self.section(f"Connecting to {endpoint}...")
            client = self.sdk.ProGloveClient(endpoint)
            client.send_ping()
            self.success("Connected!")

            self.section("Performing OTA update...")

            def on_progress(pages_sent: int, total_pages: int) -> None:
                print(f"    page {pages_sent}/{total_pages}", end="\r")

            ok = client.perform_ota(image, key, sig, on_progress, timeout)
            print()
            if ok:
                self.success("OTA update completed!")
                return 0
            else:
                self.error("OTA update failed or timed out")
                return 1

        except self.sdk.ConnectionError as e:
            self.error(f"Connection failed: {e}")
            print("\nMake sure proglove-headless-ipc-host is running")
            return 1
        except self.sdk.ProGloveError as e:
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
                    client.close()
                except Exception:
                    pass


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update ProGlove firmware over the OTA interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m proglove_demo.test_ota --status-endpoint ipc:///tmp/proglove-left-status.ipc --image firmware.bin
  python -m proglove_demo.test_ota --status-endpoint ipc:///tmp/proglove-right-status.ipc --image firmware.bin --timeout 30

Default endpoints:
  Left hand (IPC):  ipc:///tmp/proglove-left-status.ipc
  Right hand (IPC): ipc:///tmp/proglove-right-status.ipc
""",
    )
    parser.add_argument(
        "--status-endpoint",
        type=str,
        required=True,
        help="ZeroMQ status endpoint (e.g., ipc:///tmp/proglove-left-status.ipc)",
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to the firmware binary to flash",
    )
    parser.add_argument(
        "--key-file",
        type=str,
        default=None,
        help="Path to 32-byte ed25519 public key (default: zero-filled — verification is currently unenforced firmware-side)",
    )
    parser.add_argument(
        "--sig-file",
        type=str,
        default=None,
        help="Path to 64-byte ed25519 signature (default: zero-filled — verification is currently unenforced firmware-side)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for each firmware reply before giving up (default: 15.0)",
    )
    args = parser.parse_args()

    demo = TestOtaDemo()
    return demo.run(
        args.status_endpoint, args.image, args.key_file, args.sig_file, args.timeout
    )


if __name__ == "__main__":
    sys.exit(main())
