#!/usr/bin/env bash
set -o errexit
set -o errtrace
set -o nounset
set -o pipefail

# show commands
set -o xtrace


# Default to one directory up.
CONBENCH_REPO_ROOT_DIR="${CONBENCH_REPO_ROOT_DIR:=..}"
echo "CONBENCH_REPO_ROOT_DIR: $CONBENCH_REPO_ROOT_DIR"

# assume that minikube cluster is running.
# show debug info
minikube config view
minikube status

# for https://github.com/prometheus-operator/kube-prometheus
minikube addons disable metrics-server

# This project vastly simplifies setting up PostgreSQL in minikube for us:
# https://postgres-operator.readthedocs.io
#
# Great docs: https://postgres-operator.readthedocs.io/en/latest/user/
#
# Use this manifest by running ./run_operator_locally.sh
# https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml
git clone https://github.com/zalando/postgres-operator
pushd postgres-operator
    git checkout v1.9.0 # release from 2023-01-30
    # Set up  https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml

    # alchemy: the minikube cluster is already up and running as of a previous step
    # in github actions. Remove 'clean_up' and 'start_minikube' from
    # `run_operator_locally.sh`. Do this via line number deletion. In the original
    # file, delete line 256 and 257. That is safe, because a specific commit of
    # this file was checked out.

    sed -i 's|numberOfInstances: 2|numberOfInstances: 1|g' manifests/minimal-postgres-manifest.yaml

    cat manifests/minimal-postgres-manifest.yaml | grep numberOfInstances

    cat ./run_operator_locally.sh | tail -n 15
    sed -i '256d;257d' run_operator_locally.sh
    cat ./run_operator_locally.sh | tail -n 15
    bash ./run_operator_locally.sh
popd

# Show what's running now.
kubectl get pods -A

# In the PostgreSQL cluster the user 'zalando' has superuser privileges. Can of
# course rename that user if we'd like to, by modifying
# minimal-postgres-manifest.yaml. Get password:
export POSTGRES_CONBENCH_USER_PASSWORD="$(kubectl get secret zalando.acid-minimal-cluster.credentials.postgresql.acid.zalan.do -o 'jsonpath={.data.password}' | base64 -d)"
echo "password: ${POSTGRES_CONBENCH_USER_PASSWORD}"

# Set static non-sensitive configuration.
kubectl apply -f ${CONBENCH_REPO_ROOT_DIR}/ci/minikube/conbench-config-for-minikube.yml

# env var GITHUB_API_TOKEN is set in the context of a github action run.
# Build dynamic sensitive configuration. If GITHUB_API_TOKEN is nto set then
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


# Set up kube-prometheus
git clone https://github.com/prometheus-operator/kube-prometheus
pushd kube-prometheus
    git checkout v0.12.0  # release from 2023-01-27
    kubectl apply --server-side -f manifests/setup
    kubectl wait \
        --for condition=Established \
        --all CustomResourceDefinition \
        --namespace=monitoring
    kubectl apply -f manifests/
popd

# It seems like on minikube with cpus=2 and memory=2000 (which is the github
# actions resource footprint, by default) it's not possible to run all of
# (conbench, kube-prometheus, postgres-operator, ...) at the same time, at
# least using meaningfull resource requests. We have the resource requests
# under control for conbench. We can also patch some resource requests before
# trying to apply manifest files. I thought we could also patch resource
# requests for already applied objects by going in with precision, but
# that's seemingly a very new concept in the k8s ecosystem:
# https://github.com/kubernetes/kubernetes/issues/104737

# show contents, inject into k8s
cat conbench-secrets-for-minikube.yml
kubectl apply -f conbench-secrets-for-minikube.yml

# Build container image and deploy Conbench into the k8s cluster. This uses a
# makefile target, i.e. the repo's root dir needs to be the current working
# directory. Regardless in which current working directory we are right now; go
# to that directory in a sub shell.
(
    cd "${CONBENCH_REPO_ROOT_DIR}" && \
        make build-conbench-container-image && \
        make deploy-on-minikube
)

# Show what's running now.
kubectl get pods -A

# At this point it's expected that the postgres stack still needs a tiny bit
# of time before it's operational.
# One could do
#   kubectl wait --timeout=90s --for=condition=Ready pods acid-minimal-cluster-0
# but Conbench has internal retrying upon DB connect error

#sleep 20
#kubectl logs deployment/conbench-deployment --all-containers

sleep 5
kubectl get pods -A

sleep 3
# kubectl describe pods/prometheus-k8s-0 --namespace monitoring

# Be sure that prometheus-operator pods are done with their setup.
kubectl wait --timeout=90s --for=condition=Ready \
    pods -l app.kubernetes.io/name=prometheus-operator -n monitoring


# Be sure that the Prometheus instances managed by the prometheus operator are
# ready (ready to scrape!). There are two instances. At the time of writing I
# am not sure which of both is scraping Conbench. Just wait for the both of
# them.
kubectl wait --timeout=90s --for=condition=Ready pods prometheus-k8s-0 -n monitoring

# looks like prometheus-k8s-1 is precisely what does not start up on GHA
# because of a resource shortage.
# kubectl wait --timeout=90s --for=condition=Ready pods prometheus-k8s-1 -n monitoring

sleep 5
# kubectl logs deployment/conbench-deployment --all-containers

sleep 5
kubectl get pods -A
sleep 5

# Wait for the readiness check to succeed, which implies responsiveness to
# /api/ping.
kubectl wait --timeout=90s --for=condition=Ready pods -l app=conbench

export CONBENCH_BASE_URL=$(minikube service conbench-service --url) && echo $CONBENCH_BASE_URL
(cd "${CONBENCH_REPO_ROOT_DIR}" && make db-populate)

sleep 10
kubectl logs deployment/conbench-deployment --all-containers
