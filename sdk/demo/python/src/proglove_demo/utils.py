"""
Utility classes and functions for ProGlove FFI demos
"""

import sys
from pathlib import Path


class DemoBase:
    """Base class for demo applications with common formatting utilities."""

    def __init__(self, title: str):
        self.title = title
        # Import SDK from relative path
        self.sdk = self._load_sdk()

    def _load_sdk(self):
        """Load the ProGlove SDK from the proglove_sdk directory."""
        # Add SDK to Python path if not already there
        sdk_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "proglove_sdk"
            / "python"
        )
        if sdk_path.exists() and str(sdk_path) not in sys.path:
            sys.path.insert(0, str(sdk_path))

        try:
            import proglove_sdk

            return proglove_sdk
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import proglove_sdk: {e}\nExpected SDK at: {sdk_path}\n"
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
