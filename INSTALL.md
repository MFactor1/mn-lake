# Lake — Installation and native builds

Lake runs with two different build paths, and neither asks much of a
developer's host machine:

- **Rust runtime** — native build with `cargo` on your own machine (Linux,
  macOS, or Windows). No cross-toolchains to configure.
- **Python coordinator** — entirely container-resident. `uv` (Astral),
  CPython, and the dependency venv all live inside the coordinator Docker
  image, so developers never install Python or uv locally; the `./coordinator`
  bind mount carries source only.

All commands live in the root `justfile`.

## Prerequisites (per platform)

| Tool | Linux | macOS | Windows |
| --- | --- | --- | --- |
| just | `dnf install just` / `apt install just` | `brew install just` | `winget install --id Casey.Just --exact` |
| Docker | docker.io | docker.io | docker.io |
| Rust (cargo + rustc) — runtime builds only | https://rustup.rs | https://rustup.rs | https://rustup.rs |
| Python / uv | — not needed, they live in the coordinator container | — | — |

## Building

From the repo root:

```sh
just                     # build both Lake processes (native cargo + uv-in-container)
just build-runtime       # rebuild only the Rust side (incremental cargo build)
just build-coordinator   # docker compose build coordinator (uv sync runs at build time)
just test                # cargo test --workspace + pytest, each in its own environment
just clean               # cargo clean (Python side lives in the image; rebuilding cleans it)
```

Artifacts: the Rust binaries land in `runtime/target/release/`; the
coordinator's uv venv lives at `/venv` inside the container (outside the
source bind mount), so the host-side `coordinator/` directory stays pure
source.

Note: while Lake's manifests are still empty placeholders, `cargo` reports
its usual manifest error and `uv sync` is skipped with a TODO — the
justfile needs no changes as code lands.

## Running both processes together (dev loop)

```sh
just up        # docker compose up: both Lake processes side by side
just down      # docker compose down
just rebuild   # docker compose build (after source changes)
```

## Uninstalling / cleaning up

- `runtime/target/` and the pytest cache are gitignored build artifacts —
  `just clean` removes the Rust side.
- The coordinator leaves nothing on the host: delete its container images and
  named volumes with `docker compose stop` + `docker compose rm`, and
  optionally `docker system prune`.
- To uninstall the toolchains themselves: `rustup --uninstall`, and
  `just`/Docker via your package manager.
