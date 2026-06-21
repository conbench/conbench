# CI Reporting

`conbench ci report` turns submitted benchmark results into a synchronous CI
diagnostic. It prints JSON or Markdown, exits with a CI-friendly status, and can
link to the dashboard report page.

## Metadata Contract

The submitted payloads must match the report selector:

- `github.commit` must equal the SHA passed to `conbench ci report --commit`.
- `github.repository` must normalize to the repository passed to `--repository`.

If benchmark payloads stamp a merge commit while the report uses a head commit,
or omit commit metadata entirely, the report will return `action_required`
because it cannot find the current run.

Set `CONBENCH_TOKEN` in the CI environment. The examples below rely on
`CONBENCH_TOKEN` instead of `--token` so the token is not placed on process
arguments; `--token` remains available for explicit local overrides.

## GitHub Actions Fragment

```yaml
- name: Run benchmarks
  run: ./scripts/run-benchmarks --output bench-results

- name: Collect current-attempt run IDs
  id: run_ids
  run: |
    RUN_IDS="$(jq -r 'if type == "array" then .[]?.run_id else .run_id end // empty' bench-results/*.json | sort -u | paste -sd, -)"
    echo "run_ids=$RUN_IDS" >> "$GITHUB_OUTPUT"

- name: Submit benchmark results
  run: |
    conbench results submit "bench-results/*.json" \
      --server "$CONBENCH_SERVER_URL" | tee conbench-submit.jsonl

- name: Render Conbench CI report
  run: |
    RUN_IDS="${{ steps.run_ids.outputs.run_ids }}"
    set +e
    conbench ci report \
      --server "$CONBENCH_SERVER_URL" \
      --repository "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
      --commit "$GITHUB_SHA" \
      ${RUN_IDS:+--run-ids "$RUN_IDS"} \
      --format markdown \
      --output conbench-report.md
    report_status=$?
    set -e

    if [ -f conbench-report.md ]; then
      cat conbench-report.md >> "$GITHUB_STEP_SUMMARY"
    fi
    exit "$report_status"
```

The shape-tolerant `jq` expression handles either a single result file or files
containing arrays during local experimentation. The submit step still expects
one Conbench result object per file, so split array-shaped output before calling
`conbench results submit`.

## Selector Modes

Use commit-wide mode when you want the simplest report:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
  --commit "$GITHUB_SHA"
```

Use current-attempt mode when the workflow emits a shared `run_id` and you only
want this CI attempt:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --repository "${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
  --commit "$GITHUB_SHA" \
  --run-ids "$RUN_IDS"
```

Use explicit run-comparison mode when you already know the contender and
baseline run IDs:

```bash
conbench ci report \
  --server "$CONBENCH_SERVER_URL" \
  --run-ids "contender-run" \
  --baseline-run-ids "baseline-run" \
  --format markdown
```

`--baseline-run-ids` is paired by position with `--run-ids`, so both lists must
have the same count. Do not combine it with `--baseline`; automatic baseline
selection and explicit run comparison are separate modes.

## Baseline Modes

Automatic baseline selection is controlled by `--baseline`:

| Mode | Meaning |
| --- | --- |
| `fork_point` | Compare against the merge base or fork point for the selected commit. This is the default PR-oriented mode. |
| `parent` | Compare against the selected commit's parent. Use this for step-by-step commit diagnostics. |
| `latest_default` | Compare against the latest known default-branch run before the selected commit. This is useful when parent or fork-point runs are unavailable. |

When a baseline run is not found, the report includes a typed baseline error
and the commits searched. The default ancestry search is bounded; if it is
exhausted, narrow the report with `--run-ids` or provide explicit
`--baseline-run-ids`.

## Report Status

The report status is chosen from the whole report, not from one page or one
row. Precedence is:

1. Request, authentication, transport, or decode errors: no report is produced;
   the CLI exits `2`.
2. `action_required`: selected runs are missing, no contender results are
   found, benchmark results contain error payloads, or commit metadata is
   missing enough that a requested baseline cannot be resolved.
3. `failure`: at least one row has a lookback z-score regression.
4. `skipped`: results exist, but no row has computable lookback z-score
   analysis. Pairwise-only changes do not make a report pass or fail.
5. `success`: at least one row has computable lookback z-score analysis and no
   higher-precedence condition applies.

`compared` counts rows where both sides were present and pairwise comparison was
attempted. `analyzed` counts rows with a computable `lookback_z_score`.
`regressions` and `improvements` count the lookback verdicts, not pairwise-only
threshold breaches.

## Row Universe

A report row represents one contender result and, when available, the matching
baseline result for the same history fingerprint. Rows are grouped under runs,
but hardware is row-level because one run can contain results from multiple
machines.

Row statuses mean:

| Status | Meaning |
| --- | --- |
| `regressed` | Lookback z-score crossed the regression threshold. |
| `improved` | Lookback z-score crossed the improvement threshold. |
| `stable` | Lookback z-score was computable and inside the threshold band. |
| `insufficient` | Pairwise comparison may exist, but there is not enough history for lookback analysis. |
| `errored` | The benchmark result contains an error payload. |
| `missing_baseline` | No matching baseline result was found. |
| `not_comparable` | The two results cannot be compared, for example because units differ. |

## Exit Codes

- `0`: report status is `success` or `skipped`.
- `1`: report status is `failure` or `action_required`.
- `2`: usage, authentication, server, or transport error.

Always publish the Markdown summary when exit code `1` is possible. That is the
case where the diagnostic is most useful.

## Scheduled Alerts

Use `conbench ci report` for synchronous pull request diagnostics. For scheduled
monitoring, create alert rules through the API or account dashboard and run
`conbench admin alerts evaluate` from operations automation. The evaluator uses
the same CI report comparison semantics and records open/resolve events in
Conbench.

For scheduled notifications, run `conbench admin alerts deliver` with
`CONBENCH_ALERT_WEBHOOK_URL` or `--webhook-url` for a generic webhook, or with
`--channel slack` plus `CONBENCH_ALERT_SLACK_WEBHOOK_URL` or
`--slack-webhook-url` for Slack incoming-webhook delivery. For repository-scoped
scheduled GitHub Checks, use `--channel github-check` with
`CONBENCH_ALERT_GITHUB_REPOSITORY` and a token that can create Check Runs. For
repository-scoped commit comments, use `--channel github-comment` with the same
repository and token configuration. For email, use `--channel email` with
`CONBENCH_ALERT_EMAIL_SMTP_ADDR`, `CONBENCH_ALERT_EMAIL_FROM`, and
`CONBENCH_ALERT_EMAIL_TO`.
Delivery uses a durable outbox over stored alert events, so retries do not
duplicate already delivered events.

See [Alerting](alerting.md) for the canonical delivery model and current
non-goals.
