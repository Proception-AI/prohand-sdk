# Proception SDK — top-level entry point.
#
# All SDK commands live in ./sdk and are forwarded here, so the same names work
# from the repo root or from inside sdk/:
#
#   just check          verify the libraries for this platform are present
#   just install [pfx]  install C/C++ libs + headers (default /usr/local)
#   just install-python install the Python SDKs into your env (uv, else pip)
#   just demo ...       runnable examples (e.g. `just demo python ping`)
#
# The sdk module is still exposed, so `just sdk <cmd>` works too.
#
# Driver host binaries are under ./driver/<platform>.

[group: 'modules']
mod sdk 'sdk/justfile'

# Show the top-level command listing.
default:
    @echo "════════════════════════════════════════════════════════════════"
    @echo "Proception SDK"
    @echo "════════════════════════════════════════════════════════════════"
    @just --list
    @echo "────────────────────────────────────────────────────────────────"
    @echo "Run from here, or from sdk/ with the same names:"
    @echo "  check              verify the libraries for this platform"
    @echo "  install [prefix]   install C/C++ libs + headers (default /usr/local)"
    @echo "  install-python     install the Python SDKs into your env (uv, else pip)"
    @echo "  demo ...           runnable examples (Python & C++)"
    @echo "════════════════════════════════════════════════════════════════"

# Verify the compiled library for THIS OS/arch is present for every SDK.
check:
    @just sdk check

# Install this platform's C/C++ library + headers into a prefix (default /usr/local; use ~/.local or sudo).
install prefix="/usr/local":
    @just sdk install "{{ prefix }}"

# Install the Python SDK packages into your active environment (uv, else pip; run inside your venv).
install-python:
    @just sdk install-python

# Runnable examples (Python & C++) — run bare for the demo listing.
demo *args:
    @just sdk demo {{ args }}
