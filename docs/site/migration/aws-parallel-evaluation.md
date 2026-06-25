# AWS Parallel Evaluation Deployment

This runbook is for standing up a temporary Conbench v2 server alongside an
existing Python/Flask Conbench deployment so maintainers can evaluate the new
dashboard and CLI before any cutover decision.

The first evaluator should be boring: separate route, no schema changes, no
benchmark writes, and a clear stop command. Treat it as an evaluation surface,
not the production cutover.

The Arrow production inventory observed on June 25, 2026 uses EKS, Kubernetes
`LoadBalancer` Services, Route53, ACM, and private RDS. The live Python app is
not a standalone EC2 process. Keep this page generic enough for other AWS
deployments, but use the Kubernetes-native path for the Arrow evaluation unless
maintainers explicitly approve another plan.

## Safety Boundaries

- Keep the existing Python deployment untouched.
- Do not run `CONBENCH_INIT_SCHEMA=true` or `CONBENCH_SEED=true` against an
  existing deployment database.
- Prefer a read-only database URL for the first UI evaluation pass.
- Keep Terraform-managed production resources read-only during discovery.
- Do not apply Kubernetes manifests to the production cluster by hand. The
  evaluator must be described in versioned infrastructure code, reviewed with a
  Terraform plan, and applied through the same approved operations path as the
  rest of the Arrow AWS deployment.
- Do not point Buildkite writers at the evaluator until the database write
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
| AWS ownership | Account id, region, resource tags, Terraform or CloudFormation owner, and who can approve changes. |
| Serving layer | EKS cluster or host, namespace, Deployment, Service, Ingress or load balancer, image tag, replica count, probes, and restart command. |
| Existing app | Public hostname, route target, container or process manager, listen port, log path, and current rollback command. |
| Database | RDS endpoint, database name, application role, read-only role, security groups, SSL requirements, backup or clone option. |
| Network | Existing public hostname, proposed evaluator hostname, TLS owner, allowed inbound ports, internal-only ports. |
| Secrets | Where Kubernetes Secrets, parameter-store values, or host env files live, who can read them, rotation process. |
| Observability | Existing logs, metrics, alarms, and disk retention. |
| Rollback | Exact command to stop the evaluator and remove public routing. |

Do not change the Python service, RDS schema, or security groups during this
inventory pass unless maintainers explicitly approve it.

## First Deployment Shape

For the Arrow AWS deployment, use a separate Kubernetes Deployment, Service,
and DNS name. Do not reuse the live `app=conbench` selector or mutate the
existing `conbench-service`.

```text
legacy Python Conbench  -> conbench-service    -> conbench.arrow-dev.org
Conbench v2 evaluator   -> conbench-v2-service -> conbench-v2.arrow-dev.org
```

Prefer an alternate hostname over a path prefix. The Svelte application and API
are designed to be served from the root of an origin unless a path-prefix
deployment is separately tested.

Choose the routing mechanism before writing the infrastructure change:

| Option | Use when | Notes |
| --- | --- | --- |
| Temporary private access only | First operator smoke. | Use `kubectl port-forward` or another approved private tunnel. No public DNS change. |
| New Kubernetes `LoadBalancer` Service | Matches the observed Arrow production shape. | Creates a separate ELB. Route53 can point `conbench-v2.arrow-dev.org` at it after approval. |
| ALB Ingress using repo templates | Matches the v2 Kubernetes template direction. | Requires the AWS load balancer controller and the deployment owner to approve the ingress group, certificate, and DNS update path. |

Because the observed Arrow resources are tagged `ManagedBy=terraform`, public
routing must be created through the Terraform-owning repository. Do not create
snowflake Kubernetes objects, console DNS records, or one-off host processes.

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

## Build Container Images

Use the same commit that maintainers are evaluating:

```bash
git fetch origin
git checkout experimental-v2
git pull --ff-only
make build
```

For AWS Kubernetes evaluation, build and push immutable images from
`Dockerfile.server` and `Dockerfile.schema`. Use the commit SHA or release
version as the image tag. Do not deploy mutable `latest` or `dev` tags to the
shared evaluation environment.

The v2 server image runs `conbench serve` with the embedded Svelte app on port
8080. The schema image is only for Alembic ownership of the frozen schema; do
not run schema initialization or migrations against production RDS during the
read-only UI evaluation.

Keep generated docs screenshots and prod-clone artifacts off the server unless
they are part of a deliberate review bundle.

## Kubernetes Evaluator Sketch

Create separate evaluator objects rather than patching the production
Deployment. The names below are illustrative; keep the real resources in the
Terraform-owning repository so they can be planned, reviewed, applied, and
destroyed reproducibly.

Minimum evaluator objects:

- `Deployment/conbench-v2-deployment`, labels `app=conbench-v2`, one replica
  for the first read-only smoke.
- `Service/conbench-v2-service`, selector `app=conbench-v2`, port 80 to the
  server container port.
- `ConfigMap/conbench-v2-config` with `CONBENCH_ADDR=:8080` and
  `CONBENCH_INTENDED_BASE_URL=https://conbench-v2.arrow-dev.org`.
- `Secret/conbench-v2-secret` with `CONBENCH_DB_URL`, OIDC settings if enabled,
  and any GitHub token needed for read-side enrichment.

```bash
CONBENCH_ADDR=:8080
CONBENCH_INTENDED_BASE_URL=https://conbench-v2.example.org
CONBENCH_DB_URL=postgres://conbench_readonly:<secret>@rds.example:5432/conbench?sslmode=require&default_transaction_read_only=on&statement_timeout=30s&lock_timeout=2s&idle_in_transaction_session_timeout=30s
```

Do not include `CONBENCH_AUTH_DISABLED`, `CONBENCH_INIT_SCHEMA`, or
`CONBENCH_SEED`.

For an operator-only smoke before public routing, use port-forwarding from a
local temporary kubeconfig after the Terraform-managed objects exist:

```bash
kubectl -n default port-forward service/conbench-v2-service 18080:80
```

## Routing And Network

For the first evaluation, keep the evaluator private until the operator smoke
passes. Expose only the approved evaluator URL after the Deployment is ready,
the Service endpoints point only at v2 pods, and the rollback command has been
tested.

Minimum checks:

```bash
curl -fsS http://127.0.0.1:18080/api/ping
curl -fsS 'http://127.0.0.1:18080/api/runs/recent?page_size=25' >/tmp/conbench-v2-recent.json
```

If exposing a new load balancer, restrict its security group if possible and
verify the Route53 alias points only at the evaluator target. Do not expose the
database directly to reviewers.

## Evaluation Smoke

Run these checks before sharing the URL:

1. `GET /api/ping` returns `200`.
2. `GET /api/runs/recent?page_size=25` returns recent runs.
3. The home dashboard loads in a browser without console errors.
4. A representative series page loads and tooltips work.
5. A representative compare page loads.
6. A CI report page loads if the database has reportable Arrow runs.
7. The service log has no repeated database connection errors.
8. RDS metrics do not show sustained pressure from the evaluator.

For read-only evaluation, intentionally verify that write paths are not part of
the smoke. Reporter-token minting, `conbench results submit`, and GitHub
publishing should wait for the write-enabled clone or approved target.

## Buildkite And GitHub Follow-Up

After maintainers can browse the evaluator, use a write-enabled non-production
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

The read-only evaluator rollback should be immediate and should not affect the
Python service. For a Kubernetes evaluator, rollback should be a reviewed
Terraform change that removes only the v2 route and v2 objects:

```bash
terraform plan \
  -target=kubernetes_deployment.conbench_v2 \
  -target=kubernetes_service.conbench_v2 \
  -target=kubernetes_config_map.conbench_v2 \
  -target=kubernetes_secret.conbench_v2 \
  -target=aws_route53_record.conbench_v2
```

Run the matching approved apply only after reviewing the plan. Because the
first pass uses a read-only role, no database cleanup should be required.

If a later write-enabled smoke uses a cloned database, preserve the clone until
maintainers have reviewed submitted runs, Buildkite artifacts, and GitHub
output. If a write-enabled production rehearsal is ever approved, define the
cleanup and rollback plan before enabling writers.
