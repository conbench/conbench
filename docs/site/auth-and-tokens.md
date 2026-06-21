# Authentication And Tokens

Read endpoints are generally public unless a deployment is configured otherwise.
Writes and token management require authentication.

## Humans

Humans authenticate through OIDC session login. The CLI supports loopback login:

```bash
conbench auth login --server "$CONBENCH_SERVER_URL"
```

The login flow mints a user-owned API token only after the loopback exchange
completes. The CLI stores credentials in a local credentials file with tight
permissions.

The intermediate loopback code is stored server-side as a short-lived hash and
is single-use. This lets `cli-start` and `cli-exchange` land on different server
replicas without sticky routing, while avoiding storage of the plaintext code.

The web app exposes the same user-owned token model at `/account` for interactive
use. It shows the current OIDC identity, supports browser logout, lists token
prefixes and timestamps, creates new tokens, and revokes existing tokens. Token
plaintext is shown only in the creation response.

The new system does not carry forward local password login, open registration,
or general user CRUD pages. User records are created from OIDC identity during
login. The supported self-service surface is `/account`, `/api/users/me`, and
the user-owned API-token endpoints.

## Automation

Automation should use API tokens:

```bash
export CONBENCH_TOKEN=<token>
conbench results submit "bench-results/*.json" --server "$CONBENCH_SERVER_URL"
```

Token resolution order is:

1. `--token`
2. `CONBENCH_TOKEN`
3. CLI credentials file

For CI and shared scripts, prefer exporting `CONBENCH_TOKEN` and omitting
`--token`; reserve `--token` for explicit local overrides. That keeps tokens out
of normal process arguments.

## Token Management

Use the CLI for scripts and repeatable automation:

```bash
conbench auth token list --server "$CONBENCH_SERVER_URL"
conbench auth token revoke <token-id> --server "$CONBENCH_SERVER_URL"
```

The API never returns token plaintext after creation. Result submission and CI
reporting should never print the token.

There is no supported admin API for listing, editing, or deleting arbitrary
users in the current system. If a deployment needs operator user administration
later, it should be added as a separate authenticated operator feature with
explicit authorization rules.
