# Lake — one justfile for all devs (Linux, macOS, Windows).
#
# Two self-contained binaries are installed once per machine:
#   just:  Linux dnf/apt install just | macOS brew install just
#          Windows winget install --id Casey.Just --exact (or choco)
#   uv:    Linux/macOS curl -LsSf https://astral.sh/uv/install.sh | sh
#          Windows powershell irm https://astral.sh/uv/install.ps1 | iex
#          (brew install uv / apt PPA also work)
#
# Run from the repo root:
#   just                 # build both Lake processes natively
#   just test            # build, then cargo test + pytest
#   just build-runtime   # rebuild only the Rust side (incremental)
#   just build-coordinator # uv sync: wheels + CPython into coordinator/.venv
#   just run-local       # run the coordinator natively (uv run lake)
#   just up / just down  # docker dev harness for the RUNTIME engine only
#
# OS-neutral design rules this file follows:
# - On Windows recipes run in PowerShell ([windows] shell below); elsewhere
#   the default sh is used.
# - Each recipe LINE runs in its own shell invocation, so recipes never use
#   cd or &&; they use [working-directory] attributes instead, which work
#   in sh and in PowerShell equally.
# - The coordinator has NO docker layer at all: uv on the host manages the
#   wheels (from the committed uv.lock — the same drift guard as committed
#   Cargo.lock) AND the CPython interpreter itself (requires-python drives
#   an auto-download when a dev has no Python). `uv run` behaves identically
#   under sh and PowerShell, so no per-platform recipe variants are needed.
#   The host needs: just, uv, the Rust toolchain, and docker only for the
#   optional runtime compose harness.
#
# WIP status: coordinator deps are minimal (uv resolves them fine) and the
# Rust crates are stubs; recipes need no structural changes as real code
# lands. First uv sync needs network (wheel/interpreter download); after
# that everything is local and cached.

# Build both Lake processes natively for this machine (the default recipe).
[parallel]
build: build-runtime build-coordinator

[parallel]
run: run-runtime run-coordinator

[working-directory: 'runtime']
build-runtime:
    cargo build --workspace --release

[working-directory: 'coordinator']
build-coordinator:
    uv sync

[working-directory: 'coordinator']
run-coordinator:
    uv run lake

[working-directory: 'runtime']
run-runtime:
	cargo run --workspace --release

[parallel]
test: test-runtime test-coordinator

[working-directory: 'runtime']
test-runtime:
    cargo test --workspace

[working-directory: 'coordinator']
test-coordinator:
    uv run pytest -q .

clean: clean-runtime clean-coordinator

[working-directory: 'runtime']
clean-runtime:
    cargo clean

[working-directory: 'coordinator']
clean-coordinator:
    uv venv --clear .venv

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# PowerShell on Windows (default sh is used elsewhere).
[windows]
set shell := ["powershell.exe", "-NoProfile", "-NoLogo", "-Command"]
