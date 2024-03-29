#!/usr/bin/env bash
set -o errexit
set -o errtrace
set -o nounset
set -o pipefail
set -o xtrace


# Design choice for this script: assume that minikube cluster is running. Show
# debug info. We use a specific minikube profile name on local dev machines,
# but cannot yet do so on GHA.

# Special note: this script does not make an assumption about the current
# working directory. It can be/should be runnable in any directory. It however
# needs to know where the conbench repo's root directory is. Default to two
# directories up from _this_ scruptfile, for local workflows (so that this can
# be run in e.g. an ephemeral "build dir" of some kind. CI is expected to set
# CONBENCH_REPO_ROOT_DIR for precise control. Export, so that it's available to
# child processes.
_this_script_dir="$(dirname "$(realpath -s "$0")")"  # https://stackoverflow.com/a/11114547/145400
export CONBENCH_REPO_ROOT_DIR="${CONBENCH_REPO_ROOT_DIR:=$_this_script_dir/../../}"
echo "CONBENCH_REPO_ROOT_DIR: $CONBENCH_REPO_ROOT_DIR"

# Log debug info, do not crash script.
minikube config view
minikube status --profile mk-conbench || true

# A small cleanup recommended by
# https://github.com/prometheus-operator/kube-prometheus
# Unclear if actually required.
minikube addons disable metrics-server --profile mk-conbench

# For testing the ingress controller spec
minikube addons enable ingress --profile mk-conbench

# postgres-operator vastly simplifies setting up PostgreSQL in minikube for us:
# https://postgres-operator.readthedocs.io
# Great docs: https://postgres-operator.readthedocs.io/en/latest/user/
# Running ./run_operator_locally.sh means installing this manifest:
# https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml
#git clone https://github.com/zalando/postgres-operator
git clone https://github.com/jgehrcke/postgres-operator
pushd postgres-operator
    # git checkout v1.9.0  # release from 2023-01-30
    # Use this patch for better robustness for now, also see
    # https://github.com/conbench/conbench/issues/693
    # https://github.com/zalando/postgres-operator/pull/2218
    git checkout 43e2d18d900d342a4f7fbc919edd64c24ea57eac # on jp/run-local-robustness

    # Set number of Postgres instances to 1. Need to be conservative with k8s
    # cluster resources, because GHA offers limited resources.
    sed -i.bak 's|numberOfInstances: 2|numberOfInstances: 1|g' manifests/minimal-postgres-manifest.yaml
    cat manifests/minimal-postgres-manifest.yaml | grep numberOfInstances

    # Remove 'start_minikube' from `run_operator_locally.sh` (the minikube
    # cluster is already up and running at this point).
    sed -i.bak 's|^    start_minikube$|#start_minikube|g' ./run_operator_locally.sh

    bash ./run_operator_locally.sh
popd

# debuggability: show what's running now.
kubectl get pods -A

# In the PostgreSQL cluster the user 'zalando' has superuser privileges. We can
# rename that user if we'd like to by modifying minimal-postgres-manifest.yaml.
# Get password for this user (was dynamically generated during bootstrap):
# Wait until this secret is available.
until kubectl get secret zalando.acid-minimal-cluster.credentials.postgresql.acid.zalan.do
do
    echo "postgres-operator does not seem to have created the secret yet. wait."
    sleep 3
done

export POSTGRES_CONBENCH_USER_PASSWORD="$(kubectl get secret zalando.acid-minimal-cluster.credentials.postgresql.acid.zalan.do -o 'jsonpath={.data.password}' | base64 -d)"
echo "db password: ${POSTGRES_CONBENCH_USER_PASSWORD}"

# Set static non-sensitive configuration.
kubectl apply -f ${CONBENCH_REPO_ROOT_DIR}/ci/minikube/conbench-config-for-minikube.yml

# Build dynamic sensitive configuration. This was built assuming that
# GITHUB_API_TOKEN is set in the context of a GitHub Action run. If
# GITHUB_API_TOKEN is not (e.g. during local dev) then do not error out but
# default to an empty string.
cat << EOF > conbench-secrets-for-minikube.yml
apiVersion: v1
kind: Secret
metadata:
  name: conbench-secret
type: Opaque
# stringData: no base64 decoding
stringData:
  DB_PASSWORD: "${POSTGRES_CONBENCH_USER_PASSWORD}"
  DB_USERNAME: "zalando"
  GITHUB_API_TOKEN: "${GITHUB_API_TOKEN:=}"
  REGISTRATION_KEY: "innocent-registration-key"
  SECRET_KEY: "not-actually-secret"
EOF

export PROM_REMOTE_WRITE_CLUSTER_LABEL_VALUE="ci-conbench-on-$(hostname -s)"


# JSONNET-build our custom version of kube-prometheus. Before JSONNET
# compilation mutate the main document to make adjustments for the minikube
# environment (smaller resource footprint, anonymous access to Grafana UI).
export MUTATE_JSONNET_FILE_FOR_MINIKUBE=true

(
    cd "${CONBENCH_REPO_ROOT_DIR}" && \
    make jsonnet-kube-prom-manifests && \
    bash k8s/kube-prometheus/deploy-or-update.sh && \
    # Do this twice, to check for idempotency of this script.
    bash k8s/kube-prometheus/deploy-or-update.sh
)

# On minikube with cpus=2 and memory=2000 (which is the github actions resource
# footprint by default) it's certainly possible to run everything we need for
# this test here (conbench, grafana, prometheus, postgres-operator, ...) at the
# same time, even if we're oversubscribing the hardware a bit. However,
# meaningful/realistic k8s resource requests add up to more than the available
# memory/cpu. That is, we need to work around that. We have the resource
# requests under control for conbench and claim that it uses 0 of everything.
# If that is not enough e can also patch some resource requests before trying
# to apply manifest files for kube-prometheus and postgres-operator. I thought
# we could also patch resource requests for already applied objects by going in
# with precision, but that's seemingly a very new concept in the k8s ecosystem:
# https://github.com/kubernetes/kubernetes/issues/104737

cat conbench-secrets-for-minikube.yml | grep -v TOKEN
kubectl apply -f conbench-secrets-for-minikube.yml

# Deploy Conbench into the k8s cluster. This uses Makefile targets. That is,
# the repo's root dir needs to be the current working directory. Regardless in
# which current working directory we are right now; go to that directory in a
# sub shell.
(
    cd "${CONBENCH_REPO_ROOT_DIR}" && \
        make build-conbench-container-image && \
        make deploy-on-minikube
)

# The various `sleep`s below are here to have less interleaved command output
# in the GHA log viewer (the output created by set -o xtrace might otherwise
# interleave with output from previously executed commands).

# debuggability: show what's running now.
sleep 1
kubectl get pods -A

# At this point it's expected that the postgres stack still needs a tiny bit of
# time before it's operational. For now it seems this just works because
# Conbench has rather persistent internal retrying upon DB connect error.

# These commands might be useful for debugging the state of things.
# kubectl wait --timeout=90s --for=condition=Ready pods acid-minimal-cluster-0
# kubectl describe pods/prometheus-k8s-0 --namespace monitoring

# Explicitly wait for this dependency.
sleep 1
kubectl wait --timeout=90s --for=condition=Ready \
    pods -l app.kubernetes.io/name=prometheus-operator -n monitoring

# Be sure that the Prometheus instances managed by the prometheus operator are
# ready (ready to scrape!). There are two instances: both are replicas of each
# other in the same StatefulSet. Looks like prometheus-k8s-1 does not always
# start up on GHA because of a resource shortage. Explicitly wait for
# prometheus-k8s-0, to do care about -1 for now. Note that this here or a
# similar technique might allow for scheduling all requested components:
# https://github.com/prometheus-operator/kube-prometheus/blob/main/docs/customizations/strip-limits.md
sleep 1
kubectl wait --timeout=180s --for=condition=Ready pods prometheus-k8s-0 -n monitoring

sleep 5
kubectl get pods -A

# Wait for readiness check to succeed, which implies responsiveness to /api/ping.
sleep 1
kubectl wait --timeout=180s --for=condition=Ready pods -l app=conbench

sleep 5
# Require access log line confirming that the /metrics endpoint was hit.
# Temporarily disable the errexit guardrail, and also disable xtrace for
# verbosity control.
set +e
set +x
attempt=0
retries=15
wait_seconds=5
until ( kubectl logs deployment/conbench-deployment --all-containers | grep '"GET /metrics HTTP/1.1" 200' )
do
    retcode=$?
    attempt=$(($attempt + 1))
    if [ $attempt -lt $retries ]; then
        echo "pipeline returncode: $retcode -- probe not yet found in log, retry soon"
        sleep $wait_seconds
    else
        kubectl logs deployment/conbench-deployment --all-containers > conbench_container_output.log
        cat conbench_container_output.log
        exit 1
    fi
done
set -e
set -x
