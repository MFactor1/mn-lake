# Lake — one justfile for all devs (Linux, macOS, Windows).
#
# just is a single self-contained binary; install it once per machine:
#   Linux: dnf/apt install just   macOS: brew install just
#   Windows: winget install --id Casey.Just --exact  (or choco)
#
# Run from the repo root:
#   just                 # build both Lake processes natively
#   just test            # build, then cargo test + pytest
#   just build-runtime   # rebuild only the Rust side (incremental)
#   just build-coordinator # uv sync deps in the coordinator container
#   just up / just down  # docker dev loop for both processes
#
# OS-neutral design rules this file follows:
# - On Windows recipes run in PowerShell ([windows] shell below); elsewhere
#   the default sh is used.
# - Each recipe LINE runs in its own shell invocation, so recipes never use
#   cd or &&; they use [working-directory] attributes instead, which work
#   in sh and in PowerShell equally.
# - uv/venv/python management stays ENTIRELY inside the coordinator
#   container (see coordinator/Dockerfile): the host only needs just,
#   the Rust toolchain (for the native runtime), and docker.
#
# WIP status: coordinator/pyproject.toml is still an empty placeholder (uv
# sync is skipped there with a TODO), and the Rust crates are stubs — cargo
# fails where the stubs don't compile yet (engine/src/main.rs is empty).
# These recipes need no structural changes as real code lands.

# Build both Lake processes natively for this machine (the default recipe).
build: build-runtime build-coordinator

# Build the Rust runtime (binaries land in runtime/target/release/).
[working-directory: 'runtime']
build-runtime:
    cargo build --workspace --release

# Resolve/install Python deps with uv inside the coordinator image
# (uv sync layer runs at build time; devs never install uv or Python).
build-coordinator:
    docker compose build coordinator

# Run both test suites (cargo test + pytest, per the VnV plan).
test: test-runtime test-coordinator

# cargo test for the Rust side.
[working-directory: 'runtime']
test-runtime:
    cargo test --workspace

# pytest for the Python side, resolved through the container's uv env.
# Args after the service name override the image CMD.
test-coordinator: build-coordinator
    docker compose run coordinator uv run pytest -q .

# Remove local build artifacts (the Python side lives in the container
# image; rebuilding cleans it — there is nothing host-side to delete).
clean: clean-runtime

# cargo clean.
[working-directory: 'runtime']
clean-runtime:
    cargo clean

# Bring both Lake processes up together (needs docker installed).
up:
    docker compose up

# Take both Lake processes down.
down:
    docker compose down

# Rebuild both docker images after source changes.
rebuild:
    docker compose build

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# PowerShell on Windows (default sh is used elsewhere).
[windows]
set shell := ["powershell.exe", "-NoProfile", "-NoLogo", "-Command"]
