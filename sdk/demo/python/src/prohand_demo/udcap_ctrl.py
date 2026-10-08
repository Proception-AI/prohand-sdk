#!/usr/bin/env python3
"""
UDP glove capture -> ProHand control demo.
"""

import argparse
import asyncio
import json
import math
import socket
import time
from typing import Any, Optional

from .utils import DemoBase


class GloveDataMapper:
    """Maps glove data from UDP JSON to ProHand command format."""

    LEFT_JOINT_MAP = {
        "thumb": ["l20", "l2", "l1", "l0"],
        "index": ["l7", "l6", "l5", "l4"],
        "middle": ["l11", "l10", "l9", "l8"],
        "ring": ["l15", "l14", "l13", "l12"],
        "pinky": ["l19", "l18", "l17", "l16"],
    }
    RIGHT_JOINT_MAP = {
        "thumb": ["r20", "r2", "r1", "r0"],
        "index": ["r7", "r6", "r5", "r4"],
        "middle": ["r11", "r10", "r9", "r8"],
        "ring": ["r15", "r14", "r13", "r12"],
        "pinky": ["r19", "r18", "r17", "r16"],
    }
    JOINT_RANGES_DEG = {
        "thumb": [(0, 40), (-60.0, 0.0), (-60.0, 0.0), (-70.0, 10.0)],
        "index": [(-25.0, 0.0), (-80.0, 0.0), (-100.0, 0.0), (-80.0, 0.0)],
        "middle": [(-4.5, 4.5), (-80.0, 0.0), (-100.0, 0.0), (-80.0, 0.0)],
        "ring": [(0.0, 15.0), (-80.0, 0.0), (-100.0, 0.0), (-80.0, 0.0)],
        "pinky": [(0.0, 35.0), (-80.0, 0.0), (-100.0, 0.0), (-80.0, 0.0)],
    }
    ROBOT_RANGES_DEG = {
        "thumb": [(0.0, 130.0), (-30.0, 60.0), (-20.0, 90.0), (-15.0, 90.0)],
        "index": [(-15.0, 30.0), (-20.0, 90.0), (-15.0, 90.0), (0.0, 90.0)],
        "middle": [(-15.0, 15.0), (-20.0, 90.0), (-15.0, 90.0), (0.0, 90.0)],
        "ring": [(-15.0, 15.0), (-20.0, 90.0), (-15.0, 90.0), (0.0, 90.0)],
        "pinky": [(-30.0, 15.0), (-20.0, 90.0), (-15.0, 90.0), (0.0, 90.0)],
    }

    def __init__(self, hand: str = "left", verbose: bool = False):
        self.hand = hand.lower()
        self.verbose = verbose
        if self.hand not in {"left", "right"}:
            raise ValueError("hand must be 'left' or 'right'")
        self.joint_map = (
            self.LEFT_JOINT_MAP if self.hand == "left" else self.RIGHT_JOINT_MAP
        )

    def parse_udp_message(self, data: bytes) -> Optional[dict[str, Any]]:
        try:
            msg = data.decode("utf-8")
            start = msg.find('{"')
            if start == -1:
                return None
            brace = 0
            end = -1
            for i, ch in enumerate(msg[start:], start):
                if ch == "{":
                    brace += 1
                elif ch == "}":
                    brace -= 1
                    if brace == 0:
                        end = i + 1
                        break
            if end == -1:
                return None
            return json.loads(msg[start:end])
        except Exception:
            return None

    def extract_parameters(self, message_dict: dict) -> dict[str, float]:
        params: dict[str, float] = {}

        def visit(obj: Any) -> None:
            if isinstance(obj, dict):
                if "Parameter" in obj and isinstance(obj["Parameter"], list):
                    for param in obj["Parameter"]:
                        if (
                            isinstance(param, dict)
                            and "Name" in param
                            and "Value" in param
                        ):
                            name = param["Name"]
                            val = param["Value"]
                            if self.hand == "left":
                                if name.startswith("l") or not name.startswith("r"):
                                    params[name] = float(val)
                            else:
                                if name.startswith("r") or not name.startswith("l"):
                                    params[name] = float(val)
                else:
                    for value in obj.values():
                        visit(value)
            elif isinstance(obj, list):
                for item in obj:
                    visit(item)

        visit(message_dict)
        return params

    @staticmethod
    def degrees_to_radians(deg: float) -> float:
        return math.radians(deg)

    def map_to_hand_command(self, params: dict[str, float]) -> dict[str, list[float]]:
        cmd: dict[str, list[float]] = {}
        for finger_name, joint_names in self.joint_map.items():
            angles: list[float] = []
            input_ranges = self.JOINT_RANGES_DEG.get(finger_name, [(-180.0, 180.0)] * 4)
            output_ranges = self.ROBOT_RANGES_DEG.get(
                finger_name, [(-180.0, 180.0)] * 4
            )
            for i, joint in enumerate(joint_names):
                if joint in params:
                    raw = float(params[joint])
                    min_deg, max_deg = (
                        input_ranges[i] if i < len(input_ranges) else (-180.0, 180.0)
                    )
                    clamped = max(min_deg, min(max_deg, raw))
                    out_min, out_max = (
                        output_ranges[i] if i < len(output_ranges) else (-180.0, 180.0)
                    )
                    s01 = (
                        (clamped - min_deg) / (max_deg - min_deg)
                        if max_deg != min_deg
                        else 0.0
                    )
                    if not (finger_name == "thumb" and i == 0):
                        s01 = 1.0 - s01
                    angle_deg = out_min + s01 * (out_max - out_min)
                    angles.append(self.degrees_to_radians(angle_deg))
                else:
                    angles.append(0.0)
            cmd[finger_name] = angles
        cmd["wrist"] = [0.0, 0.0]
        return cmd

    def process_udp_data(self, data: bytes) -> Optional[dict[str, list[float]]]:
        msg = self.parse_udp_message(data)
        if msg is None:
            return None
        params = self.extract_parameters(msg)
        if not params:
            return None
        return self.map_to_hand_command(params)


class UdcapDemo(DemoBase):
    """Single-hand UDP->ProHand streaming demo."""

    def __init__(self):
        super().__init__("UDCAP → ProHand Demo")

    async def run(
        self,
        hand: str,
        udp_host: str,
        udp_port: int,
        command_endpoint: str,
        status_endpoint: str,
        hand_streaming_endpoint: str,
        wrist_streaming_endpoint: str,
        torque: float,
        publish_rate: float,
    ) -> int:
        self.banner()
        mapper = GloveDataMapper(hand=hand, verbose=False)
        client = self.sdk.ProHandClient(
            command_endpoint,
            status_endpoint,
            hand_streaming_endpoint,
            wrist_streaming_endpoint,
        )

        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind((udp_host, udp_port))

        try:
            await asyncio.sleep(0.05)
            client.set_streaming_mode(True)
            client.wait_for_streaming_ready(timeout=2.0, retry_interval=0.2)
        except Exception as exc:
            self.error(f"Failed to connect to ProHand: {exc}")
            self.info("Make sure prohand-headless-ipc-host is running")
            sock.close()
            return 1

        self.info(f"Listening UDP on {udp_host}:{udp_port}, streaming to ProHand.")
        publish_interval = 1.0 / publish_rate
        last_publish = time.monotonic()
        last_rx = time.monotonic()

        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        loop.sock_recv(sock, 4096), timeout=0.01
                    )
                    last_rx = time.monotonic()
                    cmd = mapper.process_udp_data(data)
                    if cmd:
                        flat: list[float] = (
                            cmd["thumb"]
                            + cmd["index"]
                            + cmd["middle"]
                            + cmd["ring"]
                            + cmd["pinky"]
                        )
                        now = time.monotonic()
                        if now - last_publish >= publish_interval:
                            client.send_hand_streams(flat, torque)
                            last_publish = now
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    if now - last_rx > 3.0:
                        self.warning("No UDP data received in last 3s; check driver")
                        last_rx = now
                    continue
        except KeyboardInterrupt:
            self.info("Interrupted by user. Stopping...")
        finally:
            sock.close()
            try:
                client.set_streaming_mode(False)
            except Exception:
                pass
            client.close()
        return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="UDCAP → ProHand demo (single hand)")
    parser.add_argument("--hand", choices=["left", "right"], default="left")
    parser.add_argument("--udp-host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=5555)
    parser.add_argument(
        "--command-endpoint",
        default="ipc:///tmp/prohand-commands.ipc",
        help="ProHand command endpoint",
    )
    parser.add_argument(
        "--status-endpoint",
        default="ipc:///tmp/prohand-status.ipc",
        help="ProHand status endpoint",
    )
    parser.add_argument(
        "--hand-streaming-endpoint",
        default="ipc:///tmp/prohand-hand-streaming.ipc",
        help="ProHand hand streaming endpoint",
    )
    parser.add_argument(
        "--wrist-streaming-endpoint",
        default="ipc:///tmp/prohand-wrist-streaming.ipc",
        help="ProHand wrist streaming endpoint",
    )
    parser.add_argument("--torque", type=float, default=0.8)
    parser.add_argument("--publish-rate", type=float, default=60.0)
    args = parser.parse_args()

    return await UdcapDemo().run(
        hand=args.hand,
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        command_endpoint=args.command_endpoint,
        status_endpoint=args.status_endpoint,
        hand_streaming_endpoint=args.hand_streaming_endpoint,
        wrist_streaming_endpoint=args.wrist_streaming_endpoint,
        torque=args.torque,
        publish_rate=args.publish_rate,
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
