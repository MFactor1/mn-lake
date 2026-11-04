# syntax=docker/dockerfile:1
#
# Lake runtime — the Rust process (inference engine on top of ggml).
# Crates: engine, ggml_rs (Lake's internal Rust-to-C FFI bindings to ggml),
# tensor-io. (If Lake ever publishes crates to crates.io, note that bare
# ggml and ggml_rs are both contested names there; publish under a prefixed
# lake-ggml instead.)
#
# Build context: ./runtime  (set by docker-compose.yml)
#   docker build -f runtime/Dockerfile -t lake-runtime runtime
#
# Linux, macOS, and Windows developers run the same commands:
#   docker compose up      |  docker compose down
#
# NOTE for macOS/Windows devs: the Rust build inside Docker produces a Linux
# binary that runs under QEMU emulation. That is fine for development, but
# expect slow link/run times on Apple Silicon and plan for cross-compilation
# when Lake ships final binaries to real edge devices.
#
# The Rust sources exist as stubs now (hello() functions, empty main.rs), so
# the build layer is unconditional; see the NOTE below about engine compiling.

FROM rust:1.99-trixie

# ggml is a C library: its Rust FFI bindings will need a C toolchain at build
# time. Cheap to include now; harmless if ggml ends up vendored differently.
RUN apt-get update \
    && apt-get install -y clang cmake pkg-config \
    && apt-get clean

WORKDIR /build

# Manifest first, then crates: cargo only recompiles when sources change.
COPY Cargo.toml .
COPY crates ./crates

# Builds all workspace crates into /build/target/release (CMD runs that path,
# so no cache-mount on target here: mounts aren't part of the image).
# NOTE: engine/src/main.rs is still an empty stub, so this layer (and
# `docker compose build runtime`) will fail until the engine crate compiles;
# native builds via `just build-runtime` are the active dev path today.
RUN cargo build --workspace --release

CMD ["/build/target/release/lake_engine"]
