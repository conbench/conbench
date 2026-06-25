# CI Run Triage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the home page a CI-run triage surface that leads with commit subject, author, counts, attention, and useful actions instead of raw run IDs.

**Architecture:** Extend the existing `/api/runs/recent` path with already-persisted commit metadata, map that into a focused Svelte view model, and replace the home table layout without adding new repository selection or run-wide hardware aggregation. Keep attention on the existing newest-five bounded path.

**Tech Stack:** Go/huma/sqlc/Postgres backend, Svelte 5 SPA, Vitest component and loader tests, Go API tests, generated OpenAPI/TypeScript schema.

---

### Task 1: Expose commit identity on recent runs

**Files:**
- Modify: `internal/db/query/benchmark_result.sql`
- Modify generated: `internal/db/benchmark_result.sql.go`
- Modify: `internal/storage/storage.go`
- Modify: `internal/db/storageport.go`
- Modify: `internal/service/list.go`
- Modify: `internal/service/runs.go`
- Test: `internal/api/list_test.go`

- [x] Write a failing API test asserting `/api/runs/recent` includes commit message, author name, author login, and author avatar in `commit` for a seeded run.
- [x] Run `go test -shuffle=on ./internal/api -run TestListRecentRunsGroupsResultsByRun` and verify it fails because the fields are absent.
- [x] Extend `ListCommit`, storage DTOs, and recent-runs SQL selection/mapping to carry the fields from `commit`.
- [x] Run `make sqlc` if available, or update generated sqlc output consistently.
- [x] Re-run the targeted Go test and verify it passes.

### Task 2: Derive CI triage view models

**Files:**
- Modify: `web/src/lib/home/loader.ts`
- Test: `web/src/lib/home/loader.test.ts`

- [x] Write failing view-model tests for primary run label = commit subject, secondary run ID = compact ID, author display/avatar fallback, GitHub commit href built client-side, and attention badge split from error count.
- [x] Run the targeted Vitest file and verify it fails for missing fields/derived labels.
- [x] Implement minimal derived fields in `loader.ts`.
- [x] Re-run the targeted Vitest file and verify it passes.

### Task 3: Redesign the home component around CI triage

**Files:**
- Modify: `web/src/lib/components/RecentRunsHome.svelte`
- Test: `web/src/lib/components/RecentRunsHome.test.ts`

- [x] Write failing component tests around behavior: derived summary state, actionable links, compact production identifiers, and column suppression. Keep commit/author text derivation covered in view-model tests.
- [x] Run the targeted component test and verify it fails for the current UUID-first UI.
- [x] Replace the current table header/columns with the dense CI-run table: time, results, reason, author, commit, message, report/actions, with UUIDs demoted.
- [x] Re-run the targeted component test and verify it passes.

### Task 4: Regenerate contracts and verify locally

**Files:**
- Generated: `api/openapi.yaml`, `api/openapi-3.0.yaml`, `web/src/lib/api/schema.ts` if API shape changes require it.

- [x] Regenerate OpenAPI, TypeScript, Go SDK, and Python SDK artifacts with the repo codegen targets.
- [x] Run focused Go and web tests.
- [x] Start the Go/Svelte app locally against the dgx-spark prod-clone database, with no AWS deployment.
- [x] Smoke `http://127.0.0.1:<port>/` and a recent-runs API request.
- [ ] Commit the completed implementation.
