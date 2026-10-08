"""
ProGlove taxel geometry for spatial (palm) visualization.

Positions are parsed from the bundled `assets/GT1_Vector_Taxels_{left,right}.svg`
(copies of the CAD source-of-truth, kept alongside the demo for stability), and
mapped from flat reading order into SVG dot order via the per-hand correction
tables. This mirrors `crates/prohand-gui-backend/build.rs` + `glove_viz_svg.rs` in the Rust GUI,
so the demo places the same 100 taxels the diagnostic GUI does.
"""

from pathlib import Path
from typing import List, Tuple

# `correction[flat_index] = svg_dot_index`: which SVG dot each flat reading maps
# to. Copied verbatim from `glove_viz_svg.rs` (touch-confirmed on hardware).
LEFT_CORRECTION = [
    0, 1, 2, 3, 4, 5, 14, 18, 19, 21, 22, 24, 23, 26, 25, 29, 6, 8, 7, 9, 10, 15, 11, 16, 13, 20,
    12, 17, 28, 36, 30, 35, 32, 38, 31, 37, 61, 75, 62, 73, 65, 69, 64, 71, 94, 99, 95, 98, 92, 96,
    93, 97, 27, 33, 41, 50, 57, 72, 81, 89, 34, 39, 46, 52, 63, 74, 80, 88, 40, 45, 51, 56, 66, 76,
    83, 91, 42, 47, 53, 58, 68, 78, 85, 90, 43, 48, 54, 60, 70, 79, 84, 87, 44, 49, 55, 59, 67, 77,
    82, 86,
]  # fmt: skip

RIGHT_CORRECTION = [
    1, 0, 3, 2, 5, 4, 18, 14, 21, 19, 24, 22, 26, 23, 29, 25, 8, 6, 9, 7, 15, 10, 16, 11, 20, 13,
    17, 12, 36, 28, 35, 30, 38, 32, 37, 31, 75, 61, 73, 62, 69, 65, 71, 64, 99, 94, 98, 95, 96, 92,
    97, 93, 89, 81, 72, 57, 50, 41, 33, 27, 88, 80, 74, 63, 52, 46, 39, 34, 91, 83, 76, 66, 56, 51,
    45, 40, 90, 85, 78, 68, 58, 53, 47, 42, 87, 84, 79, 70, 60, 54, 48, 43, 86, 82, 77, 67, 59, 55,
    49, 44,
]  # fmt: skip

TAXEL_COUNT = 100
_ASSETS = Path(__file__).parent / "assets"


def _extract_numbers(s: str) -> List[float]:
    """Tokenize SVG numbers, treating a mid-token '-' as a new number (port of
    build.rs `extract_numbers`)."""
    numbers: List[float] = []
    current = ""
    for c in s + " ":
        if c == "-" and current:
            try:
                numbers.append(float(current))
            except ValueError:
                pass
            current = ""
        if c == "-" or c == "." or c.isdigit():
            current += c
        elif current:
            try:
                numbers.append(float(current))
            except ValueError:
                pass
            current = ""
    return numbers


def _between(s: str, start: str, end: str) -> str:
    i = s.find(start)
    if i < 0:
        raise ValueError(f"missing {start!r} in path chunk")
    i += len(start)
    j = s.find(end, i)
    if j < 0:
        raise ValueError(f"missing {end!r} after {start!r}")
    return s[i:j]


def parse_taxel_positions(svg: str) -> List[Tuple[float, float]]:
    """Bounding-box midpoint of each `<path>`'s `d` curve, transformed by its
    own `matrix(...)` — one (x, y) per taxel, in raw SVG path order."""
    positions: List[Tuple[float, float]] = []
    for chunk in svg.split("<path ")[1:]:
        m = _extract_numbers(_between(chunk, "matrix(", ")"))
        if len(m) != 6:
            raise ValueError(f"expected 6-value transform matrix, got {m}")
        a, b, c, d, tx, ty = m
        coords = _extract_numbers(_between(chunk, ' d="', '"'))
        if len(coords) < 2 or len(coords) % 2 != 0:
            raise ValueError("expected an even, non-empty coordinate list in d")
        xs = coords[0::2]
        ys = coords[1::2]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        positions.append((a * cx + c * cy + tx, b * cx + d * cy + ty))
    return positions


def flat_positions(hand: str) -> List[Tuple[float, float]]:
    """Taxel (x, y) in **flat reading order** for `left`/`right`: the SVG dot
    positions reordered by the correction table so `positions[i]` is where flat
    reading `i` should be drawn."""
    svg = (_ASSETS / f"GT1_Vector_Taxels_{hand}.svg").read_text()
    dots = parse_taxel_positions(svg)
    if len(dots) != TAXEL_COUNT:
        raise ValueError(
            f"expected {TAXEL_COUNT} taxels in {hand} SVG, found {len(dots)}"
        )
    correction = LEFT_CORRECTION if hand == "left" else RIGHT_CORRECTION
    return [dots[correction[i]] for i in range(TAXEL_COUNT)]
