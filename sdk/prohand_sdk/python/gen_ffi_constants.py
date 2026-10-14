"""Write prohand_sdk/_ffi_constants.py from the C header.

The header is generated from the Rust FFI types, so the enums here follow the
SDK's own constants and never a hand copy. `just crates hand-client-sdk header`
runs this after cbindgen; tests/test_ffi_constants.py fails on drift.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parent
HEADER = PYTHON_ROOT.parent / "cpp" / "include" / "prohand_sdk" / "prohand_sdk.h"
OUTPUT = PYTHON_ROOT / "prohand_sdk" / "_ffi_constants.py"

# (class, header prefix, member filter on the stripped name, docstring)
FAMILIES = [
    (
        "ProHandResult",
        "PROHAND_",
        r"SUCCESS|ERROR_\w+",
        "Result codes returned by SDK functions.",
    ),
    (
        "CalibrationMask",
        "PROHAND_CALIB_",
        r"\w+",
        "Finger bitmask values for send_auto_calibration(). OR them together.",
    ),
    (
        "MessageKind",
        "PROHAND_MSG_",
        r"\w+",
        "Wire discriminant of `ProHandStatus`. Values are the protocol's, not ours.",
    ),
]


def members(header: str, prefix: str, keep: str) -> list[tuple[str, int]]:
    found = re.findall(rf"^#define {prefix}(\w+) (-?\d+)$", header, re.MULTILINE)
    return [(name, int(value)) for name, value in found if re.fullmatch(keep, name)]


def render(header: str) -> str:
    out = [
        '"""GENERATED from prohand_sdk.h by gen_ffi_constants.py. Do not edit."""',
        "",
        "from enum import IntEnum",
    ]
    for cls, prefix, keep, doc in FAMILIES:
        found = members(header, prefix, keep)
        if not found:
            raise SystemExit(f"no {prefix}* constants in {HEADER}")
        out += ["", "", f"class {cls}(IntEnum):", f'    """{doc}"""', ""]
        out += [f"    {name} = {value}" for name, value in found]
    return "\n".join(out) + "\n"


def main() -> None:
    expected = render(HEADER.read_text())
    if "--check" in sys.argv[1:]:
        if OUTPUT.read_text() != expected:
            raise SystemExit(
                f"{OUTPUT} is stale: run `just crates hand-client-sdk header`"
            )
        print(f"{OUTPUT.name} matches the header", file=sys.stderr)
        return
    OUTPUT.write_text(expected)
    print(f"wrote {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
