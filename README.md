# Lake

Developer Names:
- Colin Chambachan
- Jinwoo Hong
- Matthew Nesbitt
- Gary Qin
- Ethan Walsh

Date of project start:
September 8, 2026

Distributed artificial intelligence inference for local edge devices.

The folders and files for this project are as follows:

- docs: Documentation for the project
- refs: Reference material used for the project, including papers
- coordinator: Python source code for the coordinator part of Lake
- runtime: Rust source code for the runtime/engine part of Lake
- test: End-to-End test cases. (Unit tests can be found with the source)

The documentation for this project is updated on the project's [GitHub page](https://capstonecegjm.github.io/Lake/).

# Install
If you're a developer, see CONTRIBUTING.md instead for developer install instructions.
## From Source
### Prerequisites
| Tool | Instructions |
| --- | --- |
| just (build runner) | https://github.com/casey/just/blob/master/README.md#installation |
| uv (Python toolchain) | https://docs.astral.sh/uv/getting-started/installation/ |
| Rustup (Rust toolchain) | https://rustup.rs |

### Building
Clone this repo, then in the repo root:
```sh
just build   # Produces output binaries.
just run     # Produces output binaries, and runs them.
```
Output artifacts are:
- Coordinator: `coordinator/.venv`. `.venv` is a Python virtual environment containing the
  coordinator and all its dependencies. You can run it by calling the entrypoint at `.venv/bin/lake`.
- Engine/runtime: `runtime/target/release/lake_engine`. This is a binary you can execute directly.
