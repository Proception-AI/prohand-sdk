"""The Python enums are the C header's constants, generated, never copied."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gen_ffi_constants


def test_generated_constants_match_the_header() -> None:
    expected = gen_ffi_constants.render(gen_ffi_constants.HEADER.read_text())
    assert gen_ffi_constants.OUTPUT.read_text() == expected, (
        "prohand_sdk/_ffi_constants.py is stale: run `just crates hand-client-sdk header`"
    )


def test_every_message_kind_the_header_defines_is_known() -> None:
    header = gen_ffi_constants.HEADER.read_text()
    kinds = gen_ffi_constants.members(header, "PROHAND_MSG_", r"\w+")
    assert ("HAND_OBSERVED_STATE", 20) in kinds
    assert ("HAND_HEALTH", 21) in kinds
