#!/usr/bin/env python3
"""
ProWristCam SDK Demo: Live JPEG Viewer

Opens a GUI window that displays live JPEG frames from the wrist camera
IPC stream in real time.  Uses tkinter (stdlib) + Pillow for decoding.

Requirements:
    pip install Pillow
    # macOS: if tkinter is missing → brew install python-tk
    # Linux: if tkinter is missing → sudo apt install python3-tk
"""

from __future__ import annotations

import argparse
import io
import queue
import sys
import threading
import time
from typing import TYPE_CHECKING, Optional

from .utils import DemoBase

# ── Optional dependency checks ────────────────────────────────────────────────
# TYPE_CHECKING block gives pyright fully-typed stubs without a runtime import.
# The try/except below sets the availability flags; names stay unbound on error
# but are never used unless the flag is True.

if TYPE_CHECKING:
    import tkinter as tk
    from PIL import Image, ImageTk

_TK_AVAILABLE: bool = False
_PIL_AVAILABLE: bool = False

try:
    import tkinter as tk  # type: ignore[no-redef]

    _TK_AVAILABLE = True
except ImportError:  # pragma: no cover
    pass

try:
    from PIL import Image, ImageTk  # type: ignore[no-redef, import]

    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    pass


# ── Viewer window ─────────────────────────────────────────────────────────────


class _DecodedFrame:
    """A JPEG frame that has already been decoded to a PIL Image off the main thread."""

    __slots__ = ("img", "jpeg_size", "uid")

    def __init__(self, img: Image.Image, jpeg_size: int, uid: int):
        self.img = img
        self.jpeg_size = jpeg_size
        self.uid = uid


class ViewerApp:
    """
    Low-latency live JPEG viewer built on tkinter.

    Latency design:
    - Background thread polls frames AND decodes JPEG → PIL Image (expensive ~10ms).
    - Decoded frames are stored in a single-slot "latest frame" holder guarded by
      a lock — no queue buffering, the UI always shows the most recent decoded frame.
    - Main thread only calls ImageTk.PhotoImage() (fast, ~1ms) and updates labels.
    - UI tick runs at 60 Hz (16ms) so it picks up frames as soon as they arrive.
    """

    _BG_DARK = "#0d1117"
    _BG_BAR = "#161b22"
    _FG_LABEL = "#c9d1d9"
    _FG_LIVE = "#3fb950"
    _FG_WARN = "#d29922"
    _FG_ERROR = "#f85149"
    _FONT_MONO = ("Courier New", 11)
    _FONT_BOLD = ("Courier New", 11, "bold")

    def __init__(self, root: tk.Tk, endpoint: str, sdk):
        self.root = root
        self.endpoint = endpoint
        self.sdk = sdk

        self._running = threading.Event()
        self._running.set()
        self._client = None

        # Single-slot latest frame — background thread writes, main thread reads.
        self._slot_lock = threading.Lock()
        self._slot: Optional[_DecodedFrame] = None

        # Status messages from background thread (connection ok / error)
        self._status_queue: queue.Queue = queue.Queue()

        # Stats (main-thread only)
        self.frame_count = 0
        self._fps = 0.0
        self._fps_count = 0
        self._fps_t = time.monotonic()

        self._build_ui()

        self._poll_thread = threading.Thread(
            target=self._bg_poll, daemon=True, name="wristcam-poll"
        )
        self._poll_thread.start()

        self.root.after(16, self._tick)  # 60 Hz

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.title(f"ProWristCam Viewer — {self.endpoint}")
        self.root.configure(bg=self._BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

        self._canvas = tk.Label(
            self.root,
            bg=self._BG_DARK,
            text="Connecting …",
            fg=self._FG_WARN,
            font=("Courier New", 14),
            cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        bar = tk.Frame(self.root, bg=self._BG_BAR, pady=5)
        bar.pack(fill="x", padx=6, pady=(0, 6))

        def lbl(
            text: str, side: str = "left", fg: Optional[str] = None, bold: bool = False
        ) -> tk.Label:
            font = self._FONT_BOLD if bold else self._FONT_MONO
            widget = tk.Label(
                bar, text=text, bg=self._BG_BAR, fg=fg or self._FG_LABEL, font=font
            )
            widget.pack(side=side, padx=10)  # type: ignore[arg-type]
            return widget

        self._lbl_status = lbl("● Connecting", fg=self._FG_WARN, bold=True)
        self._lbl_fps = lbl("FPS: --")
        self._lbl_frames = lbl("Frames: 0")
        self._lbl_res = lbl("Res: --")
        self._lbl_size = lbl("--", side="right")

    # ── Background poll + decode thread ──────────────────────────────────────

    def _bg_poll(self):
        try:
            self._client = self.sdk.WristCamClient(self.endpoint)
            self._status_queue.put(("ok", None))
        except Exception as exc:
            self._status_queue.put(("error", str(exc)))
            return

        while self._running.is_set():
            try:
                frame = self._client.try_recv_frame()
                if frame and frame.jpeg:
                    # Decode JPEG here — keeps the main thread's _tick() fast.
                    raw = bytes(frame.jpeg)
                    img = Image.open(io.BytesIO(raw))
                    img.load()  # force full decode now, not lazily on main thread

                    decoded = _DecodedFrame(img, len(raw), frame.uid)

                    # Overwrite the slot — only the latest frame matters.
                    with self._slot_lock:
                        self._slot = decoded
                else:
                    time.sleep(0.001)
            except Exception:
                time.sleep(0.005)

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

    # ── Main-thread timer (60 Hz) ─────────────────────────────────────────────

    def _tick(self):
        if not self._running.is_set():
            return

        # Drain status messages (connection / error)
        try:
            while True:
                kind, data = self._status_queue.get_nowait()
                if kind == "ok":
                    self._lbl_status.configure(text="● Live", fg=self._FG_LIVE)
                elif kind == "error":
                    self._canvas.configure(
                        image="",
                        text=f"Connection error:\n{data[:60]}",
                        fg=self._FG_ERROR,
                    )
                    self._lbl_status.configure(text="✗ Error", fg=self._FG_ERROR)
        except queue.Empty:
            pass

        # Grab latest decoded frame (non-blocking)
        with self._slot_lock:
            decoded = self._slot
            self._slot = None  # consume — don't show the same frame twice

        if decoded is not None:
            self._render(decoded)

        self.root.after(16, self._tick)

    def _render(self, decoded: _DecodedFrame):
        """Paint a pre-decoded frame. Only ImageTk.PhotoImage() runs here."""
        self.frame_count += 1
        self._fps_count += 1

        now = time.monotonic()
        dt = now - self._fps_t
        if dt >= 1.0:
            self._fps = self._fps_count / dt
            self._fps_count = 0
            self._fps_t = now

        # ImageTk.PhotoImage must be created on the main thread — everything
        # else (JPEG decode, img.load) has already happened on the bg thread.
        photo = ImageTk.PhotoImage(decoded.img)
        self._canvas.configure(image=photo, text="")
        self._canvas._photo = photo  # type: ignore[attr-defined]

        self._lbl_fps.configure(text=f"FPS: {self._fps:5.1f}")
        self._lbl_frames.configure(text=f"Frames: {self.frame_count:,}")
        self._lbl_res.configure(text=f"Res: {decoded.img.width}×{decoded.img.height}")
        self._lbl_size.configure(text=f"{decoded.jpeg_size:,} B")

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _shutdown(self):
        self._running.clear()
        self.root.after(250, self.root.destroy)


# ── Demo wrapper ──────────────────────────────────────────────────────────────


class LiveViewerDemo(DemoBase):
    """Open a live GUI viewer for the wrist camera stream."""

    def __init__(self):
        super().__init__("ProWristCam Live Viewer")

    def run(self, endpoint: str) -> int:
        if not _TK_AVAILABLE:
            self.error("tkinter is not available.")
            print("  macOS: brew install python-tk")
            print("  Linux: sudo apt install python3-tk")
            return 1

        if not _PIL_AVAILABLE:
            self.error("Pillow is required for the live viewer.")
            print("  pip install Pillow")
            return 1

        self.banner()
        print(f"\n  Endpoint : {endpoint}")
        print(f"  SDK      : {self.sdk.get_version()}")
        print("\nOpening viewer window … (close window or press Ctrl+C to stop)\n")

        root = tk.Tk()
        root.geometry("900x700")
        root.minsize(400, 320)

        app = ViewerApp(root, endpoint, self.sdk)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            app._shutdown()

        return 0


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live JPEG viewer for a wrist camera stream",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m prowrist_demo.viewer
  python -m prowrist_demo.viewer --endpoint ipc:///tmp/prowristcam-left-stream.ipc
  python -m prowrist_demo.viewer --endpoint ipc:///tmp/prowristcam-right-stream.ipc
  python -m prowrist_demo.viewer --endpoint tcp://192.168.1.82:5565

Requirements:
  pip install Pillow
""",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="ipc:///tmp/prowristcam-left-stream.ipc",
        help="ZeroMQ stream endpoint (default: ipc:///tmp/prowristcam-left-stream.ipc)",
    )
    args = parser.parse_args()
    return LiveViewerDemo().run(args.endpoint)


if __name__ == "__main__":
    sys.exit(main())
