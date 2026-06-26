# Conbench V2 Evaluator Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a temporary, read-only Conbench v2 evaluator at `https://conbench-v2.arrow-dev.org` so Arrow maintainers can review the new server and UI without affecting the legacy Python deployment.

**Architecture:** Deploy a separate Kubernetes Deployment, Service, ConfigMap, Secret, and optional Route53 record from the Terraform owner repo at `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform`. The first milestone is private `ClusterIP` smoke against the production RDS read-only URL; public LoadBalancer and DNS exposure happen only after that smoke passes and each Terraform plan is reviewed.

**Tech Stack:** Terraform, AWS ECR, EKS, Kubernetes, Route53, ACM, Conbench `Dockerfile.server`, Go/Svelte server image.

---

## Current Inventory

- Conbench source repo: `/Users/wesm/code/conbench`, branch `experimental-v2`.
- IaC owner repo: `/Users/wesm/code/arrow-benchmarks-ci-v2`, branch `v2-conbench-ci-report`.
- Terraform evaluator resources already exist in `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench_v2_evaluator.tf`.
- Local ignored evaluator vars file exists at `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`.
- The local vars file is configured for private smoke:
  - `conbench_v2_enabled = true`
  - `conbench_v2_expose_load_balancer = false`
  - `conbench_v2_create_dns_record = false`
- Current AWS SSO status: `AWS_PROFILE=arrow-conbench aws ecr describe-images ...` failed with an expired SSO token. Refresh before any AWS read or write.

## Safety Rules

- Do not run `terraform apply` until the user explicitly approves the exact plan being applied.
- Do not commit `*.tfvars`, database URLs, API tokens, OIDC secrets, GitHub tokens, or environment dumps.
- Do not create one-off Kubernetes resources, Route53 records, or AWS console edits.
- Do not mutate `conbench-service`, `conbench-deployment`, `conbench-ingress`, RDS schema, or production Python Conbench.
- Do not enable Buildkite writers, reporter-token creation, or GitHub publishing against the read-only evaluator.

### Task 1: Refresh AWS SSO

**Files:**
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`
- No repository file changes.

- [ ] **Step 1: Refresh the profile**

Run:

```bash
AWS_PROFILE=arrow-conbench aws sso login
```

Expected: Browser SSO succeeds and returns to the shell without error.

- [ ] **Step 2: Verify identity**

Run:

```bash
AWS_PROFILE=arrow-conbench aws sts get-caller-identity
```

Expected: Account `855673865593` and an assumed `AdministratorAccess` role for `wes`.

- [ ] **Step 3: Record kata progress**

Run from `/Users/wesm/code/conbench`:

```bash
kata comment whnh --body "AWS SSO refreshed for arrow-conbench; ready to inspect ECR and Terraform plan for the private evaluator." --agent
```

Expected: kata comment succeeds.

### Task 2: Build And Push The Current V2 Server Image

**Files:**
- Read: `/Users/wesm/code/conbench/Dockerfile.server`
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/ecr.tf`
- Modify local ignored file only: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`

- [ ] **Step 1: Compute the immutable image tag**

Run:

```bash
cd /Users/wesm/code/conbench
git status --short --branch
git rev-parse --short=12 HEAD
```

Expected: clean `experimental-v2` worktree. Record the SHA as `SHORT_SHA`.

- [ ] **Step 2: Check whether the image already exists**

Run:

```bash
SHORT_SHA="$(git -C /Users/wesm/code/conbench rev-parse --short=12 HEAD)"
AWS_PROFILE=arrow-conbench aws ecr describe-images \
  --repository-name conbench \
  --image-ids "imageTag=v2-${SHORT_SHA}" \
  --region us-east-1 \
  --query 'imageDetails[0].imageTags' \
  --output json
```

Expected if already pushed: JSON array containing `v2-${SHORT_SHA}`.

Expected if not pushed: `ImageNotFoundException`. Continue only after confirming an ECR image push is approved.

- [ ] **Step 3: Build the server image locally**

Run:

```bash
cd /Users/wesm/code/conbench
SHORT_SHA="$(git rev-parse --short=12 HEAD)"
docker build -f Dockerfile.server -t "conbench-server:v2-${SHORT_SHA}" .
```

Expected: Docker build exits `0`.

- [ ] **Step 4: Push the image to ECR**

Run only after explicit user approval for the ECR write:

```bash
cd /Users/wesm/code/conbench
SHORT_SHA="$(git rev-parse --short=12 HEAD)"
REGISTRY="855673865593.dkr.ecr.us-east-1.amazonaws.com"
AWS_PROFILE=arrow-conbench aws ecr get-login-password --region us-east-1 |
  docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "conbench-server:v2-${SHORT_SHA}" "${REGISTRY}/conbench:v2-${SHORT_SHA}"
docker push "${REGISTRY}/conbench:v2-${SHORT_SHA}"
```

Expected: Docker push exits `0` and ECR shows the immutable tag.

- [ ] **Step 5: Update the local evaluator vars image**

Edit only the ignored local vars file so it points at the current image:

```hcl
conbench_v2_image = "855673865593.dkr.ecr.us-east-1.amazonaws.com/conbench:v2-${SHORT_SHA}"
```

Expected: `git -C /Users/wesm/code/arrow-benchmarks-ci-v2 status --short` remains clean because `*.tfvars` is ignored.

### Task 3: Validate The Terraform Configuration

**Files:**
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench_v2_evaluator.tf`
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/variables.tf`
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/CONBENCH_V2_EVALUATOR.md`
- No file changes unless validation exposes a real defect.

- [ ] **Step 1: Check formatting**

Run:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
terraform fmt -check -recursive
```

Expected: either no output and exit `0`, or a list of pre-existing unformatted files. If formatting changes are needed, run `terraform fmt -recursive`, inspect the diff, and commit formatting separately in `arrow-benchmarks-ci-v2`.

- [ ] **Step 2: Validate Terraform**

Run:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 3: Confirm the local vars file is private-smoke only**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars')
safe = {
    'aws_profile',
    'conbench_v2_enabled',
    'conbench_v2_image',
    'conbench_v2_expose_load_balancer',
    'conbench_v2_create_dns_record',
    'conbench_v2_elb_dns_name',
    'conbench_v2_elb_zone_id',
}
for line in p.read_text().splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or '=' not in stripped:
        continue
    key, value = [part.strip() for part in stripped.split('=', 1)]
    print(f'{key} = {value if key in safe else "<redacted>"}')
PY
```

Expected:

```text
conbench_v2_enabled = true
conbench_v2_expose_load_balancer = false
conbench_v2_create_dns_record = false
```

### Task 4: Produce The Private Evaluator Terraform Plan

**Files:**
- Read: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench_v2_evaluator.tf`
- Read ignored local vars: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`
- No repository file changes.

- [ ] **Step 1: Run the targeted private plan**

Run:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_config_map.conbench_v2 \
  -target=kubernetes_secret.conbench_v2 \
  -target=kubernetes_deployment.conbench_v2 \
  -target=kubernetes_service.conbench_v2
```

Expected plan:

```text
Plan: 4 to add, 0 to change, 0 to destroy.
```

Expected resources:

```text
kubernetes_config_map.conbench_v2[0]
kubernetes_secret.conbench_v2[0]
kubernetes_deployment.conbench_v2[0]
kubernetes_service.conbench_v2[0]
```

The service must be `ClusterIP`, not `LoadBalancer`, in this plan.

- [ ] **Step 2: Review for forbidden changes**

Reject the plan if it includes changes to:

```text
aws_db_instance.*
aws_security_group.*
aws_route53_record.conbench
kubernetes_deployment.conbench
kubernetes_service.conbench
kubernetes_ingress_v1.shared_ingress
```

- [ ] **Step 3: Record the reviewed plan outcome**

Run from `/Users/wesm/code/conbench`:

```bash
kata comment whnh --body "Reviewed private evaluator Terraform plan. It creates only conbench-v2 ConfigMap, Secret, Deployment, and ClusterIP Service; no legacy Conbench, RDS, security group, or Route53 changes." --agent
```

Expected: kata comment succeeds. Adjust the message if the actual plan differs.

### Task 5: Apply The Private Evaluator Plan After Approval

**Files:**
- Read ignored local vars: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`
- No repository file changes.

- [ ] **Step 1: Get explicit approval**

Ask the user to approve applying the exact private plan from Task 4. Do not proceed on a vague approval.

- [ ] **Step 2: Apply the targeted private evaluator resources**

Run only after approval:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform apply \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_config_map.conbench_v2 \
  -target=kubernetes_secret.conbench_v2 \
  -target=kubernetes_deployment.conbench_v2 \
  -target=kubernetes_service.conbench_v2
```

Expected: Terraform creates only the four private evaluator Kubernetes resources.

- [ ] **Step 3: Verify Kubernetes objects**

Run:

```bash
AWS_PROFILE=arrow-conbench aws eks update-kubeconfig \
  --region us-east-1 \
  --name conbench-prod \
  --alias arrow-conbench-prod

kubectl --context arrow-conbench-prod -n default get deploy,svc,cm,secret \
  -l app=conbench-v2
```

Expected:

```text
deployment.apps/conbench-v2-deployment
service/conbench-v2-service
configmap/conbench-v2-config
secret/conbench-v2-secret
```

The service should show `ClusterIP`.

### Task 6: Run Private Port-Forward Smoke

**Files:**
- No repository file changes.

- [ ] **Step 1: Start the port-forward**

Run and keep the process open:

```bash
kubectl --context arrow-conbench-prod \
  -n default \
  port-forward service/conbench-v2-service 18080:80
```

Expected: local `127.0.0.1:18080` forwards to the evaluator service.

- [ ] **Step 2: Smoke the API**

Run from another shell:

```bash
curl -fsS http://127.0.0.1:18080/api/ping
curl -fsS 'http://127.0.0.1:18080/api/runs/recent?page_size=25' >/tmp/conbench-v2-recent.json
```

Expected: `/api/ping` exits `0`; recent-runs JSON is written to `/tmp/conbench-v2-recent.json`.

- [ ] **Step 3: Smoke the browser UI**

Open:

```text
http://127.0.0.1:18080/
```

Check:

```text
Home page loads.
Project selector includes apache/arrow and apache/arrow-go.
A representative run page loads.
A representative series page loads and chart tooltips respond.
A representative compare page loads.
Browser console has no repeated application errors.
```

- [ ] **Step 4: Check pod logs**

Run:

```bash
kubectl --context arrow-conbench-prod -n default logs deploy/conbench-v2-deployment --tail=200
```

Expected: no repeated database connection failures, panics, or read timeout loops.

### Task 7: Expose The LoadBalancer After Private Smoke

**Files:**
- Modify local ignored file only: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`

- [ ] **Step 1: Enable LoadBalancer only**

Set in the ignored local vars file:

```hcl
conbench_v2_expose_load_balancer = true
conbench_v2_create_dns_record    = false
```

- [ ] **Step 2: Plan the service exposure**

Run:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_service.conbench_v2
```

Expected: plan changes only `kubernetes_service.conbench_v2[0]` from `ClusterIP` to `LoadBalancer`.

- [ ] **Step 3: Apply only after approval**

Run only after explicit user approval:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform apply \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=kubernetes_service.conbench_v2
```

Expected: service becomes `LoadBalancer`.

- [ ] **Step 4: Capture the ELB hostname**

Run:

```bash
kubectl --context arrow-conbench-prod \
  -n default \
  get svc conbench-v2-service \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Expected: AWS ELB hostname is printed.

### Task 8: Add Public DNS After LoadBalancer Smoke

**Files:**
- Modify local ignored file only: `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench-v2-evaluator.tfvars`

- [ ] **Step 1: Configure DNS variables locally**

Set in the ignored local vars file:

```hcl
conbench_v2_expose_load_balancer = true
conbench_v2_create_dns_record    = true
conbench_v2_elb_dns_name         = "<captured ELB hostname>"
conbench_v2_elb_zone_id          = "Z35SXDOTRQ7X7K"
```

- [ ] **Step 2: Plan Route53**

Run:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform plan \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=aws_route53_record.conbench_v2
```

Expected: plan creates only `aws_route53_record.conbench_v2[0]` for `conbench-v2.arrow-dev.org`.

- [ ] **Step 3: Apply only after approval**

Run only after explicit user approval:

```bash
cd /Users/wesm/code/arrow-benchmarks-ci-v2/terraform
AWS_PROFILE=arrow-conbench terraform apply \
  -var-file=conbench-v2-evaluator.tfvars \
  -target=aws_route53_record.conbench_v2
```

Expected: Route53 alias is created for `conbench-v2.arrow-dev.org`.

- [ ] **Step 4: Public smoke**

Run:

```bash
curl -fsS https://conbench-v2.arrow-dev.org/api/ping
curl -fsS 'https://conbench-v2.arrow-dev.org/api/runs/recent?page_size=25' >/tmp/conbench-v2-public-recent.json
```

Expected: both commands exit `0`.

Open:

```text
https://conbench-v2.arrow-dev.org/
```

Expected: the dashboard loads with production-shaped read-only data.

### Task 9: Close The Deployment Issue

**Files:**
- No repository file changes unless a documented IaC or plan defect was fixed.

- [ ] **Step 1: Record final evidence**

Run from `/Users/wesm/code/conbench` after the public smoke passes:

```bash
kata close whnh --done \
  --message "Published the read-only Conbench v2 evaluator at https://conbench-v2.arrow-dev.org using Terraform-managed conbench-v2 resources; verified API ping, recent-runs, home UI, representative run, series, and compare pages." \
  --evidence "url:https://conbench-v2.arrow-dev.org/" \
  --agent
```

Expected: issue `whnh` is closed with URL evidence.

---

## Self-Review

- Spec coverage: the plan covers private evaluator creation, immutable image push, read-only database safety, private smoke, public LoadBalancer exposure, Route53 DNS, and rollback-safe approval checkpoints.
- Placeholder scan: no placeholder markers or unspecified implementation steps remain.
- Type consistency: Terraform variable and resource names match `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/conbench_v2_evaluator.tf` and `/Users/wesm/code/arrow-benchmarks-ci-v2/terraform/variables.tf`.
