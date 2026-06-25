# AWS Sidecar Evaluation Deployment

This runbook is for standing up a temporary Conbench v2 server next to an
existing Python/Flask Conbench deployment so maintainers can evaluate the new
dashboard and CLI before any cutover decision.

The first sidecar should be boring: same host as the current Python server,
alternate port, no schema changes, no benchmark writes, and a clear stop
command. Treat it as an evaluation surface, not the production cutover.

## Safety Boundaries

- Keep the existing Python deployment untouched.
- Do not run `CONBENCH_INIT_SCHEMA=true` or `CONBENCH_SEED=true` against an
  existing deployment database.
- Prefer a read-only database URL for the first UI evaluation pass.
- Do not point Buildkite writers at the sidecar until the database write
  strategy is explicit and approved.
- Do not use `CONBENCH_AUTH_DISABLED=true` on a shared host.
- Store database URLs, OIDC secrets, GitHub tokens, and reporter tokens in host
  secret files or the existing deployment secret manager, not in git.

Read-only mode is enough for dashboard review because Conbench read endpoints
are public by default. It is not enough for reporter submission, token
management, or first-time OIDC login if the login would need to create user
rows. Those belong in a later write-enabled smoke against a clone or an
explicitly approved production target.

## Inventory Before Changes

Before installing anything, record the current deployment shape:

| Item | What to capture |
| --- | --- |
| Host | Instance id, hostname, OS, CPU, memory, disk free, current service user. |
| Existing app | Python service manager, listen port, reverse proxy route, log path, restart command. |
| Database | RDS endpoint, database name, application role, read-only role, security groups, SSL requirements. |
| Network | Existing public hostname, TLS owner, allowed inbound ports, internal-only ports. |
| Secrets | Where app env files live, who can read them, rotation process. |
| Observability | Existing logs, metrics, alarms, and disk retention. |
| Rollback | Exact command to stop the sidecar and remove public routing. |

Do not change the Python service, RDS schema, or security groups during this
inventory pass unless maintainers explicitly approve it.

## First Deployment Shape

Run the sidecar on loopback or a private interface and expose it through an
alternate port or temporary hostname:

```text
existing Python Conbench  -> current port and route
Conbench v2 sidecar       -> 127.0.0.1:8081 or another unused local port
public evaluator URL      -> temporary port or hostname routed to the sidecar
```

Prefer an alternate hostname or explicit port over a path prefix. The Svelte
application and API are designed to be served from the root of an origin unless
a path-prefix deployment is separately tested.

## Database Strategy

Choose one database mode before starting the service:

| Mode | Use when | Notes |
| --- | --- | --- |
| Production RDS, read-only role | First dashboard kick-the-tires pass. | Lowest blast radius. UI reads work; writes, token creation, and first-time OIDC user creation should be considered unavailable. |
| Restored RDS snapshot or clone | Buildkite submit, reporter-token, and GitHub report smoke. | Preferred for write validation because it can accept v2 writes without mutating production data. |
| Production RDS, write-enabled role | Final cutover rehearsal only after maintainer approval. | Requires rollback, monitoring, and a plan for mixed Python/v2 writes. |

For the first pass, use a URL like this, with real credentials supplied through
a secret file:

```bash
CONBENCH_DB_URL='postgres://conbench_readonly:<secret>@rds.example:5432/conbench?sslmode=require&default_transaction_read_only=on&statement_timeout=30s&lock_timeout=2s&idle_in_transaction_session_timeout=30s'
```

The application should receive a single `CONBENCH_DB_URL`, not separate legacy
`DB_HOST`, `DB_USER`, or password-era Flask variables.

## Build Or Install The Server

Use the same commit that maintainers are evaluating:

```bash
git fetch origin
git checkout experimental-v2
git pull --ff-only
make build
```

For a container-based host, use `Dockerfile.server`. For a systemd sidecar on
the existing instance, install the built `bin/conbench` under a versioned path,
for example:

```bash
sudo install -d -m 0755 /opt/conbench-v2/bin
sudo install -m 0755 bin/conbench /opt/conbench-v2/bin/conbench
```

Keep generated docs screenshots and prod-clone artifacts off the server unless
they are part of a deliberate review bundle.

## Systemd Sidecar Example

Put secrets in an environment file readable only by root and the service user:

```bash
sudo install -d -m 0750 /etc/conbench-v2
sudo install -m 0640 /dev/null /etc/conbench-v2/env
```

Example `/etc/conbench-v2/env`:

```bash
CONBENCH_ADDR=127.0.0.1:8081
CONBENCH_DB_URL=postgres://conbench_readonly:<secret>@rds.example:5432/conbench?sslmode=require&default_transaction_read_only=on&statement_timeout=30s&lock_timeout=2s&idle_in_transaction_session_timeout=30s
CONBENCH_INTENDED_BASE_URL=https://conbench-v2.example.org
```

Do not include `CONBENCH_AUTH_DISABLED`, `CONBENCH_INIT_SCHEMA`, or
`CONBENCH_SEED`.

Example unit:

```ini
[Unit]
Description=Conbench v2 evaluation sidecar
After=network-online.target
Wants=network-online.target

[Service]
User=conbench
Group=conbench
EnvironmentFile=/etc/conbench-v2/env
ExecStart=/opt/conbench-v2/bin/conbench serve
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Start and inspect:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now conbench-v2
sudo systemctl status conbench-v2 --no-pager
journalctl -u conbench-v2 -n 100 --no-pager
```

## Reverse Proxy And Network

For the first evaluation, keep the sidecar listener private and expose only the
approved evaluator URL or alternate port. If the existing host already uses a
reverse proxy, add a temporary route to `127.0.0.1:8081`.

Minimum checks:

```bash
curl -fsS http://127.0.0.1:8081/api/ping
curl -fsS 'http://127.0.0.1:8081/api/runs/recent?page_size=25' >/tmp/conbench-v2-recent.json
```

If exposing a raw alternate port, restrict the security group to the expected
reviewer networks. Do not expose the database directly to reviewers.

## Evaluation Smoke

Run these checks before sharing the URL:

1. `GET /api/ping` returns `200`.
2. `GET /api/runs/recent?page_size=25` returns recent runs.
3. The home dashboard loads in a browser without console errors.
4. A representative series page loads and tooltips work.
5. A representative compare page loads.
6. A CI report page loads if the database has reportable Arrow runs.
7. The service log has no repeated database connection errors.
8. RDS metrics do not show sustained pressure from the sidecar.

For read-only evaluation, intentionally verify that write paths are not part of
the smoke. Reporter-token minting, `conbench results submit`, and GitHub
publishing should wait for the write-enabled clone or approved target.

## Buildkite And GitHub Follow-Up

After maintainers can browse the sidecar, use a write-enabled non-production
target for CI validation:

1. Mint a server-backed reporter token with `conbench admin tokens create`.
2. Store the plaintext as Buildkite `CONBENCH_TOKEN`.
3. Configure `CONBENCH_URL` to the non-production v2 endpoint.
4. Run the adapter preflight from the `wesm/arrow-benchmarks-ci` evaluation
   branch.
5. Run one Python benchmark smoke and one R benchmark smoke.
6. Run `conbench ci report` without GitHub publishing.
7. Validate GitHub App Check/comment output against a scratch pull request.

Only after that path is understood should maintainers decide whether production
Buildkite jobs can write to the v2 server.

## Rollback

The read-only sidecar rollback should be immediate and should not affect the
Python service:

```bash
sudo systemctl disable --now conbench-v2
sudo rm -f /etc/systemd/system/conbench-v2.service
sudo systemctl daemon-reload
```

Then remove the temporary reverse-proxy route or inbound port rule. Because the
first pass uses a read-only role, no database cleanup should be required.

If a later write-enabled smoke uses a cloned database, preserve the clone until
maintainers have reviewed submitted runs, Buildkite artifacts, and GitHub
output. If a write-enabled production rehearsal is ever approved, define the
cleanup and rollback plan before enabling writers.
