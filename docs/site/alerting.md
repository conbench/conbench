# Alerting

Server-side alerting is the long-running counterpart to `conbench ci report`.
It stores alert rules in Conbench, evaluates them against recent submitted runs,
and records state-transition events when a regression opens or resolves.

This replaces `benchalerts` as a maintained Conbench responsibility. The old
Python alert orchestration package is not kept as a compatibility layer.

## Model

An alert rule belongs to one authenticated Conbench user and contains:

- a repository URL,
- a baseline selector: `fork_point`, `parent`, or `latest_default`,
- pairwise and lookback z-score thresholds,
- an optional `run_reason` filter,
- an enabled flag,
- the current state: `inactive` or `open`.

The evaluator finds the latest matching run for the rule, runs the same CI
report comparison engine used by `conbench ci report`, and then updates state:

| Report status | Inactive rule | Open rule |
| --- | --- | --- |
| `failure` | create an `opened` event and mark open | leave open |
| `success` | leave inactive | create a `resolved` event and mark inactive |
| `skipped` or `action_required` | leave unchanged | leave unchanged |

Alert events store the CI report status, status reason, repository snapshot,
run id, commit SHA, report URL, and report summary JSON so operators can inspect
why the state changed.

The web app includes an `/account` surface for authenticated users to create
rules, inspect rule state, delete rules, and drill into recent events. This is
the human dashboard; the evaluator and scripted management still live in the
single `conbench` binary and authenticated API.

## API

Alert rules are managed through authenticated user APIs:

- `POST /api/alert-rules`
- `GET /api/alert-rules`
- `GET /api/alert-rules/{id}`
- `PUT /api/alert-rules/{id}`
- `DELETE /api/alert-rules/{id}`
- `GET /api/alert-rules/{id}/events`

These endpoints require a user principal from a session or user-owned API token.
The static operator token is not enough because rules are user-owned. Unknown
rule ids and rules owned by another user both return `404`.

## Evaluation

Run the evaluator from the single `conbench` binary:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_INTENDED_BASE_URL="https://conbench.example"

conbench admin alerts evaluate --format json
```

The command evaluates all enabled rules. It prints the summary to stdout and
diagnostics to stderr. It does not require `GITHUB_API_TOKEN`; it uses commit
metadata already present in the database.

Use a scheduler such as cron, Kubernetes CronJob, or your deployment platform's
job runner to call the command. Start against a production clone when changing
cadence or rule volume.

`CONBENCH_INTENDED_BASE_URL` is optional for evaluation, but set it in deployed
environments so generated report URLs are absolute and useful from logs or
notification systems.

## Delivery Channels

Conbench can deliver stored alert events to operator-configured generic webhook,
Slack incoming-webhook, GitHub Check Run, GitHub commit-comment, or SMTP email
targets. Delivery is server-owned and uses a durable outbox keyed by alert
event, channel, and target, so rerunning the command does not resend events that
were already marked delivered.

Run delivery from operations automation after evaluation:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_ALERT_WEBHOOK_URL="https://hooks.example/conbench"

conbench admin alerts deliver --format json
```

The command creates missing delivery rows for stored alert events, attempts
pending deliveries for the selected channel, marks successes as `delivered`,
and records failed attempts with `last_error`, `last_attempt_at`, and
`next_attempt_at`. Use `--limit`, `--retry-after`, and `--timeout` to bound each
run. The command does not print the database URL or target URL in summaries.

Due deliveries are claimed atomically (`FOR UPDATE SKIP LOCKED`) and leased via
`next_attempt_at` before any delivery request, so overlapping runs never send
the same delivery twice. A run that crashes mid-send leaves the row re-eligible
once its lease passes, governed by `--retry-after`. Set `--retry-after` greater
than `--timeout`; the CLI enforces this so a delivery request cannot outlive its
lease.

The webhook receives JSON with the delivery id, channel, and alert event:

```json
{
  "delivery_id": "018f...",
  "channel": "webhook",
  "event": {
    "id": "018f...",
    "rule_id": "018f...",
    "kind": "opened",
    "status": "failure",
    "status_reason": "regressions detected",
    "run_id": "run-123",
    "commit_sha": "abcdef",
    "repository": "https://github.com/org/repo",
    "report_url": "https://conbench.example/ci/report?run_ids=run-123",
    "summary": {"regressions": 1},
    "created_at": "2026-06-19T00:00:00Z"
  }
}
```

For Slack, set the Slack channel and use the Slack-specific URL flag or
environment variable:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_ALERT_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

conbench admin alerts deliver --channel slack --format json
```

Slack deliveries use the same outbox, retry, and idempotency semantics, but the
HTTP request body is a native Slack message with fallback `text` and Block Kit
sections linking to the Conbench report.

For GitHub Checks, set the repository target and provide a token with
`checks:write` access to that repository:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_ALERT_GITHUB_REPOSITORY="https://github.com/org/repo"
export GITHUB_TOKEN="..."

conbench admin alerts deliver --channel github-check --format json
```

GitHub Check delivery creates a completed Check Run on the alert event's commit.
`failure` reports become failing checks, `success` reports become successful
checks, and skipped/action-required states become neutral checks. The GitHub
Check target is a repository URL, not a webhook URL: Conbench only enqueues alert
events whose alert rule repository matches the target repository, so one
repository's alert events are not posted into another repository. Use
`CONBENCH_ALERT_GITHUB_TOKEN` when you want a delivery-specific token; the CLI
also accepts GitHub Actions' `GITHUB_TOKEN` and the existing `GITHUB_API_TOKEN`
fallback.

For GitHub commit comments, use the same repository target and token model with
`contents:write` access:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_ALERT_GITHUB_REPOSITORY="https://github.com/org/repo"
export GITHUB_TOKEN="..."

conbench admin alerts deliver --channel github-comment --format json
```

GitHub comment delivery posts a commit comment on the alert event's commit SHA.
It uses the same repository-scoped outbox behavior as GitHub Checks, so one
repository's alert events are not posted into another repository.

For email, configure an SMTP server, a sender address, and one or more
recipients:

```bash
export CONBENCH_DB_URL="postgres://..."
export CONBENCH_ALERT_EMAIL_SMTP_ADDR="smtp.example:587"
export CONBENCH_ALERT_EMAIL_FROM="Conbench Alerts <alerts@example.com>"
export CONBENCH_ALERT_EMAIL_TO="ops@example.com,perf@example.com"
export CONBENCH_ALERT_EMAIL_USERNAME="smtp-user"
export CONBENCH_ALERT_EMAIL_PASSWORD="..."

conbench admin alerts deliver --channel email --format json
```

`CONBENCH_ALERT_EMAIL_USERNAME` and `CONBENCH_ALERT_EMAIL_PASSWORD` are
optional, but must be set together when the SMTP server requires authentication.
The durable outbox target is the normalized recipient list, not the SMTP server
or password, so retries are idempotent for each alert event and recipient set.
Email delivery sends plain-text messages with the report URL, repository,
commit, run, rule, and alert event details.

## Channel Roadmap

Additional notification systems should be added as server-owned delivery
channels over the same persisted alert events and delivery outbox, not by
keeping or rebuilding `benchalerts`. Each channel should record idempotent
delivery state and test against stored alert events rather than direct CI job
callbacks.

Do not resurrect `benchalerts` as a maintained Python client package.
