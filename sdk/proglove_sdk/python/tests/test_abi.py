"""The C header, the ctypes wrapper and the built library describe one ABI."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path

import pytest

PACKAGE = "proglove_sdk"
LIBRARY_ENV = "PROGLOVE_SDK_LIB"
LIBRARY = "libproglove_client_sdk"
PREFIX = "proglove_"
SDK_ROOT = Path(__file__).resolve().parents[2]
HEADER = SDK_ROOT / "cpp" / "include" / PACKAGE / f"{PACKAGE}.h"
WRAPPER = SDK_ROOT / "python" / PACKAGE / f"{PACKAGE}.py"


def header_functions() -> set[str]:
    return set(re.findall(rf"\b({PREFIX}[a-z0-9_]+)\(", HEADER.read_text()))


def wrapper_functions() -> set[str]:
    return set(
        re.findall(rf"_lib\.({PREFIX}[a-z0-9_]+)\.argtypes", WRAPPER.read_text())
    )


def test_wrapper_binds_every_header_function() -> None:
    assert header_functions(), f"no functions found in {HEADER}"
    assert wrapper_functions() == header_functions()


def library_for_this_host() -> Path | None:
    system, machine = platform.system(), platform.machine()
    if system == "Darwin":
        name = f"{LIBRARY}.dylib"
    elif system == "Linux" and machine in ("aarch64", "arm64"):
        name = f"{LIBRARY}_aarch64.so"
    elif system == "Linux":
        name = f"{LIBRARY}.so"
    else:
        return None
    return SDK_ROOT / "lib" / name


def test_library_loads_and_reports_a_version() -> None:
    """A library that is present must load and pass the wrapper's import-time checks."""
    library = library_for_this_host()
    if library is None:
        pytest.skip(f"no {PACKAGE} library is shipped for {platform.system()}")
    if not library.is_file() and LIBRARY_ENV not in os.environ:
        pytest.skip(f"{library.name} is not built; run `just build-all` in sdk/")
    sdk = __import__(PACKAGE)
    assert sdk.get_version()
