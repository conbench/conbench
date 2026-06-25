# Conbench

Language-independent continuous benchmarking: clients publish benchmark results
as JSON to a server (API + dashboard) that persists them for regression
detection and comparison over time.

## Active work — rewrite on branch `new-vision`

Rewriting Conbench as a Go (huma/OpenAPI) backend + Svelte 5 SPA on the existing,
frozen Postgres schema. Greenfield on the API and clients; faithful port of the
analysis core (history, SVS, z-scores). Public product, migration, and
operations documentation lives in `docs/site/`; active implementation work is
tracked in kata.

The legacy Flask app source has been deleted from `new-vision`; migration
guidance and retained reference data document the cutover path. Work is tracked
in kata (project `conbench`).

## Agent workflow

- Commit repository changes before ending the turn unless the user explicitly
  asks not to commit. Keep unrelated user changes out of commits; stage only
  the paths you changed for the task.
- Do not add tautological content-matching tests that only assert that strings,
  labels, headings, or resource names you just wrote are still present. Tests
  must verify behavior or a meaningful contract: parse structured output when
  possible, exercise code paths, validate rendered artifacts with an external
  consumer, or check invariants that would catch a real regression.

## Go development (new-vision backend)

The Go backend (`cmd/`, `internal/`) follows the standards below. They are
enforced by `prek` hooks (`prek.toml`) and `.golangci.yml`; install the hooks
once with `prek install`.

- `make go-lint` — golangci-lint with `--fix` (local); `make go-lint-ci` is the
  check-only variant for CI
- `make go-test` — full suite (`-shuffle=on`); `make go-test-short` skips the
  Postgres-backed tests, so it needs no Docker
- `make go-vet`, `make go-fmt`

Conventions:

- Prefer the standard library; justify each new dependency.
- Use `huma` for HTTP routing and OpenAPI generation; do not hand-roll routes.
- Datetimes are UTC across the storage and API boundaries. Keep timestamps in
  UTC; local-time conversion belongs in the Svelte UI. `time.Local`,
  `time.LoadLocation`, and `time.FixedZone` are banned in backend code by the
  linter.
- Do the task requested, not the task imagined. Do not widen scope without
  confirming first.
- Before adding a backwards-compatibility shim, alias, or fallback wrapper, ask
  for express permission — these carry high maintenance cost.
- No emojis in code or output.

### Testing

- **Use `testify` for all Go test assertions.** Prefer `require` for
  setup/preconditions (it stops the test on failure) and `assert` for
  non-blocking checks. `t.Fatal`, `t.Fatalf`, `t.Error`, `t.Errorf`, `t.Fail`,
  and `t.FailNow` are banned by the linter — use testify instead.
- Use table-driven tests where they read well.
- Tests exercise real Postgres via `internal/dbtest` (testcontainers), never
  mocks; they skip gracefully when Docker is absent or under `go test -short`.
- Always pass `-shuffle=on` when invoking `go test` directly. Do not pass
  `-count=1` (it is the default and needlessly disables the build cache) or `-v`
  (default output has enough signal). Use `-count=N` only for `N > 1` (flake
  hunting).
- Use `t.TempDir()` for temporary directories.

<!-- BEGIN KATA (managed by `kata init --with-agents`) -->
## kata issue tracker

This project uses [kata](https://github.com/kenn-io/kata) as its shared issue
ledger. Run `kata quickstart` at the start of each session for the full agent
contract. The short version:

- Search before creating: `kata search "<keywords>" --agent`.
- Prefer updating existing issues over duplicates (`kata comment`, `kata label add`, `kata edit`).
- Default to `--agent` for ordinary reads and mutations; use `--json` only when a script needs structured data.
- Close only verified work: `kata close <ref> --done --message "<scope + verification>" --commit <sha>`.
- If work is incomplete, label `needs-review` and comment what remains rather than closing.
- Never `kata delete` or `kata purge` without explicit user authorization.
<!-- END KATA -->
