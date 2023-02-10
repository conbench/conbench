#!/usr/bin/env bash
set -o errexit
set -o errtrace
set -o nounset
set -o pipefail
set -o xtrace


# Default to one directory up, for local workflows. CI sets
# CONBENCH_REPO_ROOT_DIR for tighter control.
CONBENCH_REPO_ROOT_DIR="${CONBENCH_REPO_ROOT_DIR:=..}"
echo "CONBENCH_REPO_ROOT_DIR: $CONBENCH_REPO_ROOT_DIR"

# Design choice for this script: assume that minikube cluster is running. Show
# debug info. We use a specific minikube profile name on local dev machines,
# but cannot yet do so on GHA.

# "minikube" is the default minikube profile name that a minikube instance gets
# when started with default parameters.
export MINIKUBE_PROFILE_NAME="minikube"
if [ -z "${GITHUB_ACTION:=}" ]; then
     # Not set, or set to emtpy string. Means: not executing in the context of
     # a GitHub Action. Assume: local dev env. Use a non-default minikube
     # profile name. (see https://github.com/medyagh/setup-minikube/issues/59)
    export MINIKUBE_PROFILE_NAME="mk-conbench"
fi

minikube config view
minikube status --profile "${MINIKUBE_PROFILE_NAME}"


# A small cleanup recommended by
# https://github.com/prometheus-operator/kube-prometheus
# Unclear if actually required.
minikube addons disable metrics-server --profile "${MINIKUBE_PROFILE_NAME}"

# postgres-operator vastly simplifies setting up PostgreSQL in minikube for us:
# https://postgres-operator.readthedocs.io
# Great docs: https://postgres-operator.readthedocs.io/en/latest/user/
# Running ./run_operator_locally.sh means installing this manifest:
# https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml
git clone https://github.com/zalando/postgres-operator
pushd postgres-operator
    git checkout v1.9.0  # release from 2023-01-30

    # Set number of Postgres instances to 1. Need to be conservative with k8s
    # cluster resources, because GHA offers limited resources.
    sed -i.bak 's|numberOfInstances: 2|numberOfInstances: 1|g' manifests/minimal-postgres-manifest.yaml
    cat manifests/minimal-postgres-manifest.yaml | grep numberOfInstances

    # Timeout after four minutes instead of one minute. On some platforms this
    # takes longish. See https://github.com/conbench/conbench/issues/693.
    sed -i.bak 's|{1..20}|{1..80}|g' ./run_operator_locally.sh

    # alchemy: Remove 'clean_up' and 'start_minikube' from
    # `run_operator_locally.sh` (the minikube cluster is already up and running
    # at this point). Do this via line number deletion. In the original file,
    # delete line 256 and 257. That is safe, because a specific commit of this
    # file was checked out.
    cat ./run_operator_locally.sh | tail -n 15
    sed -i.bak '256d;257d' run_operator_locally.sh
    cat ./run_operator_locally.sh | tail -n 15
    bash ./run_operator_locally.sh
popd

# debuggability. show what's running now.
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


# Build custom version of kube-prometheus stack
( cd "${CONBENCH_REPO_ROOT_DIR}" && make jsonnet-kube-prom-manifests )

# Set up the kube-prometheus stack. This follows the customization instructions
# at https://github.com/prometheus-operator/kube-prometheus/blob/v0.12.0/docs/customizing.md
pushd "${CONBENCH_REPO_ROOT_DIR}"/_kpbuild/cb-kube-prometheus/
    kubectl apply --server-side -f manifests/setup
    kubectl wait \
        --for condition=Established \
        --all CustomResourceDefinition \
        --namespace=monitoring
    kubectl apply -f manifests/
popd


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

# Show contents (do not show api token), inject into k8s
cat conbench-secrets-for-minikube.yml | grep -v TOKEN
kubectl apply -f conbench-secrets-for-minikube.yml

# Build container image and deploy Conbench into the k8s cluster. This uses
# Makefile targets, i.e. the repo's root dir needs to be the current working
# directory. Regardless in which current working directory we are right now; go
# to that directory in a sub shell.
(
    cd "${CONBENCH_REPO_ROOT_DIR}" && \
        make build-conbench-container-image && \
        make deploy-on-minikube
)

# The various `sleep`s below are also here to have less interleaved command
# output in the GHA log viewer (the output created by set -o xtrace might
# otherwise interleave with output from previously executed commands.

# debuggability: show what's running now.
kubectl get pods -A

# At this point it's expected that the postgres stack still needs a tiny bit
# of time before it's operational.
# One could do
#   kubectl wait --timeout=90s --for=condition=Ready pods acid-minimal-cluster-0
# but for now it seems this just works because Conbench has rather persistent
# internal retrying upon DB connect error.

# sleep 20
# kubectl logs deployment/conbench-deployment --all-containers

sleep 5
kubectl get pods -A

# kubectl describe pods/prometheus-k8s-0 --namespace monitoring

# Explicitly wait for this dependency.
sleep 1
kubectl wait --timeout=90s --for=condition=Ready \
    pods -l app.kubernetes.io/name=prometheus-operator -n monitoring

# Be sure that the Prometheus instances managed by the prometheus operator are
# ready (ready to scrape!). There are two instances. At the time of writing it
# appears as if prometheus-k8s-0 is reproducibly scraping Conbench. Looks like
# prometheus-k8s-1 does not always start up on GHA because of a resource
# shortage. Explicitly wait for prometheus-k8s-0, to do care about -1 for now.
# Note that this here or a similar technique might allow for scheduling all
# requested components:
# https://github.com/prometheus-operator/kube-prometheus/blob/main/docs/customizations/strip-limits.md
sleep 1
kubectl wait --timeout=90s --for=condition=Ready pods prometheus-k8s-0 -n monitoring


# kubectl wait --timeout=90s --for=condition=Ready pods prometheus-k8s-1 -n monitoring
# sleep 1
# kubectl logs deployment/conbench-deployment --all-containers

sleep 5
kubectl get pods -A

# Wait for the readiness check to succeed, which implies responsiveness to
# /api/ping.
sleep 1
kubectl wait --timeout=90s --for=condition=Ready pods -l app=conbench

export CONBENCH_BASE_URL=$(minikube --profile "${MINIKUBE_PROFILE_NAME}" service conbench-service --url) && echo $CONBENCH_BASE_URL
# (cd "${CONBENCH_REPO_ROOT_DIR}" && make db-populate)

sleep 5
kubectl logs deployment/conbench-deployment --all-containers > conbench_container_output.log
# show in logs
cat conbench_container_output.log

# Require access log line confirming that the /metrics endpoint was hit.
# Temporarily disable the errexit guardrail, and also disable xtrace for
# verbosity control.
set +e
set +x
attempt=0
retries=10
wait_seconds=3
until ( kubectl logs deployment/conbench-deployment --all-containers | grep '"GET /metrics HTTP/1.1" 200' )
do
    retcode=$?
    attempt=$(($attempt + 1))
    if [ $attempt -lt $retries ]; then
        echo "pipeline returncode: $retcode -- probe not yet found in log, retry soon"
        sleep $wait_seconds
    else
        exit 1
    fi
done
set -e
set -x

