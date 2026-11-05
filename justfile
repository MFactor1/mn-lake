# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

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
	cargo run --release

test: test-runtime test-coordinator

[working-directory: 'runtime']
test-runtime:
	cargo test --workspace

[working-directory: 'coordinator']
test-coordinator:
	uv run pytest .

lint: lint-runtime lint-coordinator

[working-directory: 'runtime']
lint-runtime:
	cargo fmt --all -- \
		--config format_code_in_doc_comments=true \
		--config imports_layout=HorizontalVertical \
		--config imports_granularity=Module \
		--config group_imports=StdExternalCrate \
		--config overflow_delimited_expr=true
	cargo clippy --workspace --all-targets --fix --allow-dirty

[working-directory: 'coordinator']
lint-coordinator:
	uv run ruff format .
	uv run ruff check --fix

check: check-runtime check-coordinator

[working-directory: 'runtime']
check-runtime:
	cargo fmt --all --check -- \
		--config format_code_in_doc_comments=true \
		--config imports_layout=HorizontalVertical \
		--config imports_granularity=Module \
		--config group_imports=StdExternalCrate \
		--config overflow_delimited_expr=true
	cargo clippy --workspace --all-targets

[working-directory: 'coordinator']
check-coordinator:
	uv run ruff format . --check
	uv run ruff check

clean: clean-runtime clean-coordinator

[working-directory: 'runtime']
clean-runtime:
	cargo clean

[unix]
[working-directory: 'coordinator']
clean-coordinator:
	rm -rf .venv

[windows]
[working-directory: 'coordinator']
clean-coordinator:
	Remove-Item -Recurse -Force .venv

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# PowerShell on Windows (default sh is used elsewhere).
[windows]
set shell := ["powershell.exe", "-NoProfile", "-NoLogo", "-Command"]
