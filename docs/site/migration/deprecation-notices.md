# Legacy Package Deprecation Notices

Use this page when announcing the maintained Conbench cutover in package
READMEs, PyPI project descriptions, release notes, GitHub issues, or migration
pull requests. The goal is to give existing users a direct replacement path
without promising source-compatible shims for retired packages.

## General Notice

```text
This package belongs to the retired Python/Flask Conbench implementation. The
maintained Conbench system uses a Go server, Svelte dashboard, `conbench` CLI,
OpenAPI, and generated SDKs.

Do not build new automation on this package. For writes, emit Conbench result
JSON and submit it with `conbench results submit`. For pull request diagnostics,
run `conbench ci report`. For read automation, use the generated Python SDK
package named `conbench` or direct OpenAPI calls.

There is no new `conbench_client` package. The new SDK distribution and import
package are both named `conbench`.

Migration guide:
https://conbench.github.io/conbench/migration/python-app/

Legacy parity roadmap:
https://conbench.github.io/conbench/migration/legacy-parity-roadmap/
```

## `benchadapt`

```text
`benchadapt` is retired as a maintained Conbench package. Keep the useful
payload-construction idea, but do not depend on the import path as a
compatibility contract.

Migration path:
1. Build or normalize result dictionaries in your benchmark project.
2. Set `run_id`, `run_reason`, `run_tags`, `github.repository`,
   `github.commit`, `timestamp`, and `machine_info`.
3. Write payload JSON files containing one result object or an array of result
   objects.
4. Submit with `conbench results submit "bench-results/*.json"`. Use `--jobs`
   for large suites after measuring server capacity.

The maintained `conbench` SDK now ships `conbench.migration` for this bridge:
it writes payload JSON and invokes the Go CLI without becoming a
source-compatible `benchadapt` port.

Runnable migration recipe:
https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py
```

## `benchconnect`

```text
`benchconnect` is retired. Replace `benchconnect submit` and direct POST helper
usage with the Go CLI:

conbench results submit "bench-results/*.json" \
  --server "$CONBENCH_SERVER_URL" \
  --jobs 16

The new submit path uses user-owned API tokens, explicit run metadata, and
payload JSON files containing one result object or an array of result objects.
It does not preserve password-login sessions, implicit run lifecycle helpers, or
legacy client-side request augmentation.

Runnable migration recipe:
https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py
```

## `benchclients`

```text
`benchclients` is retired. Replace password/session HTTP client code with:

- the `conbench` CLI for writes and CI reports,
- the generated Python SDK package named `conbench` for reads,
- direct OpenAPI calls only when a generated SDK operation is not appropriate.

The old Flask application package and the new generated SDK both use the
`conbench` Python import name. Avoid mixed environments where both are
installed.
```

## `benchalerts`

```text
`benchalerts` is retired as a maintained Python client package.

For synchronous pull request diagnostics, run `conbench ci report` after result
submission. Use its exit status and Markdown output for CI summaries, and enable
`--github-check --github-pr-comment` when the old workflow posted GitHub App
Check Runs and pull request comments.

Scheduled alert state now belongs to the Conbench server. Create alert rules
through the `/account` dashboard or authenticated alert-rule API, then run
`conbench admin alerts evaluate` from operations automation.

For scheduled notification delivery, run `conbench admin alerts deliver` with
`CONBENCH_ALERT_WEBHOOK_URL` or `--webhook-url` for a generic webhook. For
Slack incoming-webhook delivery, use `--channel slack` with
`CONBENCH_ALERT_SLACK_WEBHOOK_URL` or `--slack-webhook-url`. For
repository-scoped scheduled GitHub Checks, use `--channel github-check` with
`CONBENCH_ALERT_GITHUB_REPOSITORY` and a token that can create Check Runs.
For repository-scoped scheduled GitHub commit comments, use
`--channel github-comment` with the same repository and token configuration.
For email delivery, use `--channel email` with
`CONBENCH_ALERT_EMAIL_SMTP_ADDR`, `CONBENCH_ALERT_EMAIL_FROM`, and
`CONBENCH_ALERT_EMAIL_TO`. These are server-owned delivery paths over the same
outbox, not a reason to keep `benchalerts`.
```

## `benchrun` And `conbenchlegacy`

```text
`benchrun` and `conbenchlegacy` are retired. Benchmark orchestration should live
in the benchmark project or in a future narrowly scoped helper justified by
real migration evidence.

Migration path:
1. Keep the benchmark execution code that is still useful.
2. Emit Conbench result JSON at the boundary.
3. Submit with the Go `conbench` CLI.
4. Remove old decorators, runner imports, and console-script assumptions after
   the JSON/CLI path is working.

The old `conbenchlegacy` console script can conflict conceptually with the new
Go `conbench` binary. Migration jobs should call the Go binary explicitly.

Runnable migration recipe:
https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py
```

## Retired Flask App Package

```text
The Python/Flask Conbench application package is retired. The maintained server
is the Go `conbench serve` binary with a Svelte dashboard and OpenAPI.

Operators should migrate deployments to the Go server image and use the
documented operations guide. Application code should stop relying on Flask
routes, Jinja templates, password-login sessions, SQLAlchemy application
objects, or Flask-specific configuration names.
```

## Community Proposal Checklist

When proposing the cutover to a benchmark community or deployment owner, include:

- the migration guide link:
  https://conbench.github.io/conbench/migration/python-app/,
- the legacy parity roadmap link:
  https://conbench.github.io/conbench/migration/legacy-parity-roadmap/,
- the runnable migration recipe link:
  https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py,
- the supported write path: `conbench results submit`,
- the supported CI path: `conbench ci report`,
- the supported Python read client: generated SDK package `conbench`,
- a note that source-compatible imports are intentionally not promised,
- a note that old package distributions may remain available for pinning during
  migration even though they are no longer maintained.

## Publication Runbook

Use this runbook when a maintainer is ready to publish the retirement message
outside this repository. It turns the copy blocks above into a concrete release
task without requiring a source-compatible package shim.

1. Identify the discovery surfaces users still see for each retired package:
   PyPI project description, package README, GitHub repository README,
   release notes, pinned docs pages, and open migration issues or pull requests.
2. Use the package-specific block above as the package README/PyPI
   long-description notice. Use the general notice for mixed pages that mention
   more than one retired package.
3. Preserve old package distributions unless there is a security or legal
   reason to remove them. The notice should make the package retired, not break
   pinned environments that still need time to migrate.
4. Link to the migration guide, the parity roadmap, and the runnable
   `examples/migration/gbench_to_cli_submit.py` recipe from every publication
   surface.
5. For `benchalerts`, include both replacements: synchronous PR diagnostics via
   `conbench ci report` including optional GitHub Check/PR-comment publishing,
   and scheduled notification state/delivery through server alert rules plus
   `conbench admin alerts evaluate` and `conbench admin alerts deliver`.
6. For the Flask `conbench` package and `conbenchlegacy`, warn explicitly about
   import and console-script name confusion. The generated SDK imports as
   `conbench`; migration jobs should call the Go `conbench` binary explicitly.

Post-publication verification:

- open each public package/discovery page in a clean browser session and verify
  the retirement notice is visible without requiring repository context,
- confirm every notice links back to the migration guide, parity roadmap, and
  runnable migration recipe,
- confirm no notice promises source-compatible `benchadapt`, `benchconnect`,
  `benchclients`, `benchalerts`, `benchrun`, `conbenchlegacy`, or
  `conbench_client` imports,
- record the published URLs in the migration tracking notes for that deployment
  or package.
