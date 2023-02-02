#!/usr/bin/env bash
set -o errexit
set -o errtrace
set -o nounset
set -o pipefail

# show commands
set -o xtrace

# This project vastly simplifies setting up PostgreSQL in minikube for us:
# https://postgres-operator.readthedocs.io
#
# Great docs: https://postgres-operator.readthedocs.io/en/latest/user/
#
# Use this manifest by running ./run_operator_locally.sh
# https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml


git clone https://github.com/zalando/postgres-operator
cd postgres-operator
# 1.9.0 release from 2023-01-30
git checkout 30b612489a2a20d968262791857d1db1a85e0b36

# This should tear down the current minikube, and re-spawn another
# one, bootstrapping the postgres operator using
# https://github.com/zalando/postgres-operator/blob/v1.9.0/manifests/minimal-postgres-manifest.yaml
bash ./run_operator_locally.sh

# Show what's running now.
kubectl get pods -A

# In the PostgreSQL cluster the user 'zalando' has superuser privileges. Can of
# course rename that user if we'd like to, by modifying
# minimal-postgres-manifest.yaml. Get password:
export POSTGRES_CONBENCH_USER_PASSWORD="$(kubectl get secret zalando.acid-minimal-cluster.credentials.postgresql.acid.zalan.do -o 'jsonpath={.data.password}' | base64 -d)"
echo "password: ${POSTGRES_CONBENCH_USER_PASSWORD}"

# Set static non-sensitive configuration.
kubectl apply -f ci/minikube/conbench-config-for-minikube.yml

# Build dynamic sensitive configuration
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
  GITHUB_API_TOKEN: "noo"
  REGISTRATION_KEY: "innocent-registration-key"
  SECRET_KEY: "not-actually-secret"
EOF

# show contents.
cat conbench-secrets-for-minikube.yml

# inject into k8s
kubectl apply -f conbench-secrets-for-minikube.yml
