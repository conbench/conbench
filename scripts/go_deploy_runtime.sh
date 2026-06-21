#!/bin/bash

export CONBENCH_SERVER_IMAGE_NAME="${CONBENCH_SERVER_IMAGE_NAME:-conbench-server}"
export CONBENCH_SCHEMA_IMAGE_NAME="${CONBENCH_SCHEMA_IMAGE_NAME:-conbench-schema}"
if [[ -z "${CONBENCH_DEPLOY_VERSION:-}" ]]; then
  echo "CONBENCH_DEPLOY_VERSION must be set to the immutable image tag for this deployment" >&2
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 1
  fi
  exit 1
fi
export CONBENCH_SERVER_IMAGE_SPEC="${DOCKER_REGISTRY}/${CONBENCH_SERVER_IMAGE_NAME}:${CONBENCH_DEPLOY_VERSION}"
export CONBENCH_SCHEMA_IMAGE_SPEC="${DOCKER_REGISTRY}/${CONBENCH_SCHEMA_IMAGE_NAME}:${CONBENCH_DEPLOY_VERSION}"
export CONBENCH_ADDR="${CONBENCH_ADDR:-:8080}"

# This script assumes that secrets have been injected via environment before
# executing this logic. That is, secrets are available here as values of a
# specific set of well-known environment variables. Not all of these
# configuration parameters are secrets. Non-sensitive parameter names include:
#
# CONBENCH_INTENDED_BASE_URL (scheme and DNS name)
# EKS_CLUSTER (the name of the EKS cluster to operate on)
# NAMESPACE (indicating the k8s namespace to deploy into)
# ...

urlencode() {
  python3 -c 'import sys; from urllib.parse import quote; print(quote(sys.stdin.read(), safe=""))'
}

build_conbench_db_url() {
  local restore_xtrace=0
  case "$-" in
    *x*)
      restore_xtrace=1
      set +x
      ;;
  esac

  local user password host port db
  for key in DB_USERNAME DB_PASSWORD DB_HOST DB_PORT DB_NAME; do
    if [[ -z "${!key:-}" ]]; then
      echo "$key must be set" >&2
      if ((restore_xtrace)); then
        set -x
      fi
      return 1
    fi
  done
  user="$(printf '%s' "${DB_USERNAME}" | urlencode)"
  password="$(printf '%s' "${DB_PASSWORD}" | urlencode)"
  host="${DB_HOST}"
  port="${DB_PORT}"
  db="$(printf '%s' "${DB_NAME}" | urlencode)"
  printf 'postgres://%s:%s@%s:%s/%s?sslmode=disable' "$user" "$password" "$host" "$port" "$db"

  if ((restore_xtrace)); then
    set -x
  fi
}

validate_intended_base_url() {
  case "${CONBENCH_INTENDED_BASE_URL:-}" in
    http://*|https://*) return 0 ;;
    *)
      echo "CONBENCH_INTENDED_BASE_URL must be set to an http(s) URL" >&2
      return 1
      ;;
  esac
}

render_template_from_env() {
  local template="$1"
  shift
  python3 - "$template" "$@" <<'PY'
import os
import pathlib
import re
import sys

template = pathlib.Path(sys.argv[1])
keys = sys.argv[2:]
text = template.read_text()

for key in keys:
    value = os.environ.get(key)
    if value is None or value == "":
        raise SystemExit(f"{key} must be set to a non-empty value to render {template}")
    text = text.replace("{{" + key + "}}", value)
    text = text.replace("<" + key + ">", value)

unresolved = sorted(
    set(re.findall(r"{{[A-Z0-9_]+}}", text))
    | set(re.findall(r"<[A-Z0-9_]+>", text))
)
if unresolved:
    raise SystemExit(f"unresolved placeholders in {template}: {', '.join(unresolved)}")
sys.stdout.write(text)
PY
}

render_secret_manifest() {
  local restore_xtrace=0
  case "$-" in
    *x*)
      restore_xtrace=1
      set +x
      ;;
  esac

  if ! validate_intended_base_url; then
    if ((restore_xtrace)); then
      set -x
    fi
    return 1
  fi

  local key
  for key in DB_PASSWORD DB_USERNAME; do
    if [[ -z "${!key:-}" ]]; then
      echo "$key must be set" >&2
      if ((restore_xtrace)); then
        set -x
      fi
      return 1
    fi
  done

  local conbench_db_url
  if ! conbench_db_url="$(build_conbench_db_url)"; then
    if ((restore_xtrace)); then
      set -x
    fi
    return 1
  fi

  local session_secret oidc_issuer oidc_client_id oidc_client_secret oidc_enabled
  session_secret="${CONBENCH_SESSION_SECRET:-}"
  oidc_issuer="${CONBENCH_OIDC_ISSUER_URL:-}"
  oidc_client_id="${CONBENCH_OIDC_CLIENT_ID:-${GOOGLE_CLIENT_ID:-}}"
  oidc_client_secret="${CONBENCH_OIDC_CLIENT_SECRET:-${GOOGLE_CLIENT_SECRET:-}}"
  if [[ -z "$oidc_issuer" && -n "${GOOGLE_CLIENT_ID:-}" && -n "${GOOGLE_CLIENT_SECRET:-}" ]]; then
    oidc_issuer="https://accounts.google.com"
  fi

  oidc_enabled=0
  if [[ -n "${CONBENCH_OIDC_ISSUER_URL:-}" || -n "${CONBENCH_OIDC_CLIENT_ID:-}" || -n "${CONBENCH_OIDC_CLIENT_SECRET:-}" || -n "${GOOGLE_CLIENT_ID:-}" || -n "${GOOGLE_CLIENT_SECRET:-}" ]]; then
    oidc_enabled=1
  fi

  if [[ "$oidc_enabled" == "1" ]]; then
    if [[ -z "$oidc_issuer" || -z "$oidc_client_id" || -z "$oidc_client_secret" ]]; then
      echo "OIDC requires complete issuer, client id, and client secret configuration" >&2
      if ((restore_xtrace)); then
        set -x
      fi
      return 1
    fi
    if ((${#session_secret} < 32)); then
      echo "CONBENCH_SESSION_SECRET must be at least 32 characters when OIDC is enabled" >&2
      if ((restore_xtrace)); then
        set -x
      fi
      return 1
    fi
  fi

  local render_status
  CONBENCH_DB_URL_RENDERED="$conbench_db_url" \
  OIDC_ENABLED="$oidc_enabled" \
  OIDC_ISSUER_RENDERED="$oidc_issuer" \
  OIDC_CLIENT_ID_RENDERED="$oidc_client_id" \
  OIDC_CLIENT_SECRET_RENDERED="$oidc_client_secret" \
  CONBENCH_SESSION_SECRET_RENDERED="$session_secret" \
  python3 <<'PY'
import base64
import json
import os
import sys

data = {
    "CONBENCH_DB_URL": os.environ["CONBENCH_DB_URL_RENDERED"],
    "CONBENCH_API_TOKEN": os.environ.get("CONBENCH_API_TOKEN", ""),
    "GITHUB_API_TOKEN": os.environ.get("GITHUB_API_TOKEN", ""),
}

if os.environ["OIDC_ENABLED"] == "1":
    data.update(
        {
            "CONBENCH_SESSION_SECRET": os.environ["CONBENCH_SESSION_SECRET_RENDERED"],
            "CONBENCH_OIDC_ISSUER_URL": os.environ["OIDC_ISSUER_RENDERED"],
            "CONBENCH_OIDC_CLIENT_ID": os.environ["OIDC_CLIENT_ID_RENDERED"],
            "CONBENCH_OIDC_CLIENT_SECRET": os.environ["OIDC_CLIENT_SECRET_RENDERED"],
        }
    )

encoded = {
    key: base64.b64encode(value.encode()).decode()
    for key, value in data.items()
}

json.dump(
    {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "conbench-secret"},
        "type": "Opaque",
        "data": encoded,
    },
    sys.stdout,
    separators=(",", ":"),
)
sys.stdout.write("\n")
PY
  render_status=$?

  if ((restore_xtrace)); then
    set -x
  fi
  return "$render_status"
}

render_config_manifest() {
  python3 <<'PY'
import json
import os
import sys

keys = [
    "CONBENCH_ADDR",
    "CONBENCH_INTENDED_BASE_URL",
]
missing = [key for key in keys if os.environ.get(key, "") == ""]
if missing:
    raise SystemExit(f"missing or empty ConfigMap values: {', '.join(missing)}")

json.dump(
    {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "conbench-config", "labels": {"app": "conbench"}},
        "data": {key: os.environ[key] for key in keys},
    },
    sys.stdout,
    separators=(",", ":"),
)
sys.stdout.write("\n")
PY
}

render_deployment_manifest() {
  render_template_from_env k8s/conbench-deployment.templ.yml CONBENCH_SERVER_IMAGE_SPEC
}

render_migration_manifest() {
  render_template_from_env k8s/conbench-db-migration.templ.yml CONBENCH_SCHEMA_IMAGE_SPEC
}

render_ingress_manifest() {
  validate_intended_base_url || return 1
  local intended_dns_name
  intended_dns_name="$(python3 <<'PY'
import os
from urllib.parse import urlparse

parsed = urlparse(os.environ["CONBENCH_INTENDED_BASE_URL"])
if not parsed.hostname:
    raise SystemExit("CONBENCH_INTENDED_BASE_URL must include a DNS name")
print(parsed.hostname)
PY
)" || return 1
  CONBENCH_INTENDED_DNS_NAME="$intended_dns_name" \
    render_template_from_env k8s/conbench-cloud-ingress.templ.yml \
      CERTIFICATE_ARN \
      CONBENCH_INTENDED_DNS_NAME
}

apply_service_monitor_if_supported() {
  if kubectl get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1; then
    kubectl apply -f k8s/conbench-service-monitor.yml || return 1
  else
    echo "skip ServiceMonitor apply; servicemonitors.monitoring.coreos.com CRD not found"
  fi
}

build_and_push() {
  set -x
  docker build -f Dockerfile.server -t "${CONBENCH_SERVER_IMAGE_NAME}" .
  docker build -f Dockerfile.schema -t "${CONBENCH_SCHEMA_IMAGE_NAME}" .
  docker images | grep conbench

  docker tag "${CONBENCH_SERVER_IMAGE_NAME}:latest" "${CONBENCH_SERVER_IMAGE_SPEC}"
  docker tag "${CONBENCH_SCHEMA_IMAGE_NAME}:latest" "${CONBENCH_SCHEMA_IMAGE_SPEC}"
  aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin "${DOCKER_REGISTRY}"
  docker push "${CONBENCH_SERVER_IMAGE_SPEC}"
  docker push "${CONBENCH_SCHEMA_IMAGE_SPEC}"
}

deploy_secrets_and_config() {
  validate_intended_base_url || return 1

  aws eks --region us-east-2 update-kubeconfig --name "${EKS_CLUSTER}"
  kubectl config set-context --current --namespace="${NAMESPACE}"

  render_secret_manifest | kubectl apply -f - || return 1
  render_config_manifest | kubectl apply -f - || return 1
}

run_migrations() {
  set -x

  aws eks --region us-east-2 update-kubeconfig --name "${EKS_CLUSTER}"
  kubectl config set-context --current --namespace="${NAMESPACE}"

  render_migration_manifest > _jobspec || return 1

  # Delete job first -- why is that important?
  kubectl delete --ignore-not-found=true -f _jobspec
  kubectl apply -f _jobspec

  # Note(JP): we give this 24 hours of time. Why? For those heavy migration
  # jobs that really take so long? Interesting.
  kubectl wait --for=condition=complete --timeout=86400s job/conbench-migration

  # Get job's stdout/err. This parses this line of text to get to the pod name:
  #
  # Normal  SuccessfulCreate  10m    job-controller  Created pod: conbench-migration-wpcp5
  export JOB_POD_NAME="$(kubectl describe job conbench-migration | grep SuccessfulCreate | tail -n1 | awk '{print $7}')"
  kubectl logs --all-containers "${JOB_POD_NAME}"

  # Can't we do this kind of err handling in the `wait` command?
  (($(kubectl get job conbench-migration -o jsonpath={.status.succeeded}) == "1")) \
    && exit 0 || exit 1
}

deploy() {
  set -x

  # This assumes AWS credentials that have the `--group system:masters
  # --username admin` privilege, see:
  # infra/blob/0a21e9a2eee1ea158d2a2a5d216407741feb3931/conbench/app/stacks/eks/main.tf#L80
  # EKS_CLUSTER is currently "vd-2" for cb&cb-staging.
  aws eks --region us-east-2 update-kubeconfig --name "${EKS_CLUSTER}"

  # All of the following kubectl commands operate on a definite namespace.
  # NAMESPACE is something like "default" or "staging"
  kubectl config set-context --current --namespace="${NAMESPACE}"

  # (Re-)apply deployment using the image tagged by CONBENCH_DEPLOY_VERSION.
  render_deployment_manifest | kubectl apply -f - || return 1
  kubectl apply -f k8s/conbench-service.yml || return 1
  apply_service_monitor_if_supported || return 1

  if [[ "$EKS_CLUSTER" == "vd-2" || "$EKS_CLUSTER" == "ursa-2" ]]; then
    # (Re-)apply ALB ingress config. Note(JP): if this results in re-creation
    # of the ALB then we need to out-of-band update an A record in Route53,
    # because we do not yet use k8s externalDNS features.
    render_ingress_manifest | kubectl apply -f - || return 1
  else
    echo "skip k8s ingress patch"
  fi

  echo "Go runtime metrics are exposed at /metrics; design Grafana dashboards from current metrics"

  # Note(JP); this might be nonobvious, but `rollout status` waits for
  # progressDeadlineSeconds (see deployment manifast) before it exits non-zero.
  # See
  # https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#failed-deployment
  kubectl rollout status deployment/conbench-deployment
}

rollback() {
  set -x
  aws eks --region us-east-2 update-kubeconfig --name "${EKS_CLUSTER}"
  kubectl config set-context --current --namespace="${NAMESPACE}"
  kubectl rollout undo deployment.v1.apps/conbench-deployment
  kubectl rollout status deployment/conbench-deployment
}

if [[ -z "${CONBENCH_DEPLOY_NO_DISPATCH:-}" && $# -gt 0 ]]; then
  "$@"
fi
