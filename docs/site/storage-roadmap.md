# Storage Roadmap

The current new Conbench server runs on the frozen legacy Postgres schema. That
keeps migration risk low: existing deployments can restore their current
database and validate the Go/Svelte implementation against real data before any
storage-model change.

The frozen schema is not the long-term end state. Production-derived testing
has already shown that the largest deployments are in the 100M-result-row class,
with almost all data volume concentrated in the append-heavy
`benchmark_result` table. That table behaves like an analytical fact table, not
like small mutable application metadata.

## Current Evidence

Sanitized production-clone findings are recorded in
[Production-Clone Compatibility](prod-clone-compatibility.md). The important
shape is:

- `benchmark_result` dominates storage size and row count,
- small dimension tables such as commit, case, hardware, context, and info are
  tiny by comparison,
- targeted result, history, compare, and CI report paths are viable when they
  avoid broad fact-table browsing,
- broad series discovery and default browse paths are the visible cost center,
- row caps and narrower queries are useful UI guards, but they do not eliminate
  the need for a future fact-model decision.

## Decision

Use a staged combination, not a single large storage rewrite.

1. Keep the frozen legacy Postgres schema as the write source of truth through
   migration and initial cutover. This lets existing deployments restore their
   current database and run the new Go/Svelte application without rewriting
   benchmark payloads or migrating historical IDs.
2. Keep using bounded SQL and targeted indexes for product paths that must work
   against existing deployments today. The Phase 5c browse/search hardening is
   the model: constrain visible rows, avoid broad fact-table enrichment, and
   keep targeted result, history, compare, and CI report reads fast.
3. Do not rebuild the legacy Flask/BMRT cache model as the long-term answer.
   Also do not start by adding broad materialized cache tables for every
   dashboard view. Those approaches improve individual screens but keep the
   100M-row analytical fact table inside the transactional database.
4. Prove a read-only columnar analytical replica before any primary fact-store
   switch. The first candidate is DuckDB reading Parquet, with DuckLake as the
   catalog layer to test after plain Parquet establishes a lower-bound baseline.
5. Move only read-heavy service interfaces to the analytical replica after
   measured correctness, latency, and operations gates pass. Writes remain
   Postgres-backed until result identity, atomic metadata/fact linkage,
   recovery, deletes, and rollback are designed and tested.
6. Keep the public API, CLI, Python SDK, and JSON payload contract stable while
   the storage backend changes behind service interfaces.

This decision makes the next storage work a proof, not a production cutover.
Smart SQL remains the compatibility path. DuckLake/Parquet is the first
scale-out read experiment. A Postgres fact-model rewrite is deferred until the
columnar proof shows whether changing the primary database is still necessary.

## Target Shape

The target split, if the proof succeeds, is:

- Postgres for transactional application metadata: users, sessions, API
  tokens, auth configuration, expected benchmark inventory, alerting
  configuration, ingestion receipts, job state, schema metadata, and canonical
  result identity.
- A columnar analytical fact store for high-volume benchmark facts, histories,
  comparison inputs, project-health rollups, broad discovery, and possibly
  regression snapshots.

DuckLake-backed Parquet queried through DuckDB is the first cataloged candidate
to test. It offers column projection, partition pruning, file-level statistics,
and a SQL catalog without requiring Spark, Hive, or distributed services.

## Migration Path

Existing deployments should be able to move in stages:

1. Restore the existing production Postgres database into a test environment.
2. Run the new Go server and Svelte app against the frozen schema.
3. Validate read compatibility with the production-clone harness and browser
   probes.
4. Point benchmark submitters at the new `conbench` CLI, with optional
   `conbench.migration` helpers for Python jobs that need payload-file writing,
   without changing the result JSON contract.
5. Add the analytical replica as an optional read-side component.
6. Shadow selected read paths against both Postgres and the replica.
7. Switch individual read-heavy interfaces only after shadow reads match and
   rollback is a configuration change.

The analytical replica is additive. If it fails, Conbench falls back to
Postgres reads. Result IDs, repository names, run identifiers, API responses,
and submitted payloads must not change because a deployment enables the replica.

## First Proof

The first storage experiment should be read-only:

1. Export `benchmark_result` and small dimensions from a production-clone
   Postgres database to Parquet.
2. Partition facts by year and month of result timestamp.
3. Query plain Parquet with DuckDB to establish a lower-bound read baseline.
4. Register the same files through DuckLake and repeat the workload.
5. Compare current Postgres, plain Parquet, monthly DuckLake, and monthly plus
   bucketed fingerprint partitioning if needed.
6. Record only sanitized aggregate findings in the production-clone
   compatibility documentation; raw clone artifacts stay ignored under `var/`.

Start with monthly partitioning. A 100M-row, multi-year corpus gives roughly
dozens of monthly partitions, not thousands of daily partitions. Daily
partitioning risks small files and excessive metadata before there is evidence
that it helps.

Candidate physical orderings inside monthly files:

- `timestamp, history_fingerprint, run_id`,
- `history_fingerprint, timestamp`,
- `repository, history_fingerprint, timestamp`.

## Query Families To Benchmark

Benchmark the product workflows, not synthetic full scans:

- single-series history filtered by history fingerprint and ordered by commit
  timestamp,
- project attention rollups filtered by repository and recent time window,
- compare-since-baseline queries grouped by history fingerprint,
- recent run/result browsing filtered by `run_id`, `batch_id`, run reason, and
  timestamp,
- export, append, and compaction throughput.

Measure storage size, cold and warm latency, CPU time, bytes read, files
scanned versus skipped, memory use, concurrent reader behavior, export
throughput, and operational complexity.

## Proof Gates

The analytical replica is not production-ready until these gates pass against a
production-derived clone:

- Correctness: result identity, history rows, compare inputs, CI report rows,
  regression verdicts, and pagination boundaries match the Postgres-backed
  implementation for the sampled workload.
- Performance: broad discovery, default browse, rollups, and long histories are
  materially faster than Postgres, while targeted result/detail/compare/CI paths
  do not regress.
- Freshness: expected ingestion-to-query lag is measured and documented.
- Reconciliation: exports and incremental refreshes can detect missing,
  duplicated, or stale facts.
- Operations: storage size, compaction, backup/restore, observability,
  concurrent readers, and failure recovery are understood well enough to run.
- Cost: storage, export compute, refresh compute, and operator work are lower
  than continuing to scale broad analytical reads inside the transactional
  Postgres database.
- Cutover: each read-heavy service can run in shadow mode and fall back to
  Postgres without changing public API behavior.

## Service Boundary

The public API should not expose the physical storage choice. Keep storage
behind service interfaces such as:

- `ResultWriter`,
- `HistoryReader`,
- `CompareReader`,
- `ProjectHealthReader`,
- `RunBrowser`.

The current implementation can keep all interfaces Postgres-backed. A
prototype can replace only read-heavy interfaces first while ingestion remains
Postgres-backed until read-side wins are proven.

## Questions Before A Primary Fact Store

Before moving writes away from the current Postgres fact table, answer:

- what lag is acceptable between a submitted result and analytical visibility,
- where result IDs are generated,
- how partial writes are recovered,
- how metadata rows and fact rows are connected atomically,
- whether alerts can tolerate eventual consistency,
- how snapshots and rollback work after bad ingests,
- how rare deletes or compliance removals are applied.

The next production cutover decision should come from measured
production-clone workloads. Do not replace the storage model just to match an
architectural preference.
