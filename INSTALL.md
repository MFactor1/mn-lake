# Lake — Installation and native builds

Lake runs with two different build paths, and neither asks much of a
developer's host machine:

- **Rust runtime** — native build with `cargo` on your own machine (Linux,
  macOS, or Windows). No cross-toolchains to configure.
- **Python coordinator** — fully NATIVE and uv-managed. `uv` (Astral) is a
  single self-contained binary installed once per machine; it resolves every
  declared package from the committed `uv.lock` and manages the CPython
  interpreter itself (`requires-python` drives an auto-download when a dev
  has no Python). Devs never install packages, and there is **no Docker
  layer on the coordinator side at all**.

All commands live in the root `justfile`.

## Prerequisites (per platform)

| Tool | Linux | macOS | Windows |
| --- | --- | --- | --- |
| just | `dnf install just` / `apt install just` | `brew install just` | `winget install --id Casey.Just --exact` |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or `brew install uv` | `brew install uv` | `powershell.exe -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Docker — only for the runtime compose harness | docker.io | docker.io | docker.io |
| Rust (cargo + rustc) — runtime builds | https://rustup.rs | https://rustup.rs | https://rustup.rs |
| Python | — not needed; uv fetches CPython 3.15 per `requires-python` | — | — |

## Building

From the repo root:

```sh
just                     # build both Lake processes natively (cargo + uv sync)
just build-runtime       # rebuild only the Rust side (incremental cargo build)
just build-coordinator   # uv sync: wheels + CPython into coordinator/.venv
just test                # cargo test --workspace + uv-run pytest, each in its own env
just clean               # cargo clean + uv venv --clear
```

Artifacts: the Rust binaries land in `runtime/target/release/`; the
coordinator's environment lives in `coordinator/.venv` (uv's default,
gitignored, fully uv-managed).

Note: while Lake's Rust manifests are still stubs, `cargo` reports its usual
error there; the uv side already works end to end. First `uv sync` needs
network (it fetches wheels and CPython once); afterwards everything is
served from uv's local cache.

## Running both processes together (dev loop)

```sh
just up        # docker compose up: runtime service (coordinator CMD is a builder-only note;
just run-local  # ...run the coordinator natively beside it, on host port 8000)
just down      # docker compose down
just rebuild   # docker compose build (after source changes)
```

## The uv-managed coordinator environment

```sh
just build-coordinator   # uv sync: declares→lock→wheels→coordinator/.venv
just run-local           # uv run lake (implicitly syncs, then starts the server)
just test-coordinator    # uv run pytest -q . in coordinator/
```

How it stays consistent across every dev:

- `pyproject.toml` **declares** packages; the committed **`uv.lock` pins exact
  versions** — the same drift guard as the committed `Cargo.lock` on the Rust
  side, and uv re-resolves minimally when a dev adds a dependency.
- uv **prunes**: `uv sync` removes anything no longer in the lock, so
  environments cannot accumulate "works-on-my-machine" drift.
- uv manages the **interpreter** too: with `requires-python = ">=3.15"` a dev
  without CPython gets a python-build-standalone 3.15 downloaded automatically;
  `uv python list`/`uv python uninstall` inspect/trim that.
- `uv run` (lake, pytest, anything) resolves commands from `coordinator/.venv`
  identically under sh and PowerShell — one OS-neutral workflow everywhere.

## Uninstalling / cleaning up

- `runtime/target/`, `coordinator/.venv/` and the pytest cache are gitignored
  build artifacts — `just clean` removes the Rust side and empties the uv env.
- There is no coordinator container stack to tear down any more: the Python
  side leaves only `coordinator/.venv` on the host; uv itself (and its fetched
  interpreters) removes cleanly via `uv uninstall`.
- To uninstall the toolchains themselves: `rustup --uninstall`, `uv
  uninstall`, and `just`/Docker via your package manager.
