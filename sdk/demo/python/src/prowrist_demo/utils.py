"""
Utility classes and functions for ProWristCam FFI demos.
"""

import sys
from pathlib import Path


class DemoBase:
    """Base class for demo applications with common formatting utilities."""

    def __init__(self, title: str):
        self.title = title
        self.sdk = self._load_sdk()

    def _load_sdk(self):
        """Load the ProWristCam SDK from the prowrist_sdk directory."""
        sdk_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "prowrist_sdk"
            / "python"
        )
        if sdk_path.exists() and str(sdk_path) not in sys.path:
            sys.path.insert(0, str(sdk_path))

        try:
            import prowrist_sdk

            return prowrist_sdk
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import prowrist_sdk: {e}\nExpected SDK at: {sdk_path}\n"
            )

    def banner(self, width: int = 60):
        """Print a banner with the demo title."""
        print("=" * width)
        print(self.title)
        print("=" * width)

    def section(self, title: str):
        """Print a section header."""
        print(f"\n>>> {title}")

    def error(self, message: str):
        """Print an error message."""
        print(f"❌ {message}")

    def success(self, message: str):
        """Print a success message."""
        print(f"✅ {message}")

    def info(self, message: str):
        """Print an info message."""
        print(f"ℹ️  {message}")

    def warning(self, message: str):
        """Print a warning message."""
        print(f"⚠️  {message}")
