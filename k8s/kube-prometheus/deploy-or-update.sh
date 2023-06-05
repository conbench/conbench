#!/usr/bin/env bash
set -o errexit
set -o errtrace
set -o nounset
set -o pipefail
set -o xtrace


# This freshly deploys or updates the Conbench-flavored kube-prometheus stack,
# based on JSONNET compilation output. This performs tiny or bigger changes.
# For example, if a Grafana dashboard JSON file changed, then this script will
# perform the relevant change in the k8s cluster (after all, by updating a k8s
# config map). If the JSONNET compilation output refers to a newer version of
# e.g. Prometheus Operator or Grafana, then those components will be rotated in
# the k8s cluster.

# Requires CONBENCH_REPO_ROOT_DIR to be set.
# Requires kubectl to be configured against target k8s cluster.
# Requires customized/compiled kube-prometheus stack in
#     ${CONBENCH_REPO_ROOT_DIR}"/_kpbuild/cb-kube-prometheus/
#
#
# Supports two environment variables to configure external storage to
# remote_write to:
#
#    PROM_REMOTE_WRITE_PASSWORD_FILE_PATH
#    PROM_REMOTE_WRITE_USERNAME
#
# Design goal: can be run multiple times against the same k8s cluster
#     with the following behavior:
#     - if kube-prometheus stack changed, an update is performed
#       (here we largely rely on the promises of the kube-prometheus project)
#     -
#

# The kube-prometheus stack's custom JSONNET stack is configured to allow for
# monitoring the `staging` namespace. I've done this to resemble a "prod"
# environment where Conbench is deployed in a k8s namespace called `staging`.
# With that setup, the namespace needs to exist before deploying
# kube-prometheus.
# kudos to https://stackoverflow.com/a/65411733/145400
kubectl create namespace staging --dry-run=client -o yaml | kubectl apply -f -

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

if [ -z "${PROM_REMOTE_WRITE_PASSWORD_FILE_PATH:=}" ]; then
    # Not set, or set to emtpy string.
    # Set up invalid username/password for the Prometheus remote_write config.
    # remote_write will fail, and that is OK.
    _rw_passw_filepath="_prom_remote_write_password"
    echo "invalid-password" > $_rw_passw_filepath
else
    echo "${PROM_REMOTE_WRITE_PASSWORD_FILE_PATH} is set, use that password."
    _rw_passw_filepath="${PROM_REMOTE_WRITE_PASSWORD_FILE_PATH}"
fi
_rw_username="${PROM_REMOTE_WRITE_USERNAME:-invaliduser}"

# do not error out when secret already exists, replace with new value
# https://stackoverflow.com/a/45881259/145400
echo "'pusher prom' remote_write username: $_rw_username"
echo "'pusher prom' remote_write password filepath: $_rw_passw_filepath"
kubectl create secret generic kubepromsecret \
    --from-literal=username="${_rw_username}" \
    --from-file=password="${_rw_passw_filepath}" \
    -n monitoring --save-config --dry-run=client -o yaml | kubectl apply -f -
