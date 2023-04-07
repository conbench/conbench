#!/bin/bash

# Location of the Conbench web application container image. Note: it seems like
# FLASK_APP has a static value: "conbench". Maybe we should hard-code this to
# "conbench-webapp" or something like that.
export IMAGE_SPEC="${DOCKER_REGISTRY}/${FLASK_APP}:${BUILDKITE_COMMIT}"

# This script assumes that secrets have been injected via environment. (`env`
# file fetched from S3, and sourced automatically on the Buildkite runner
# before executing this logic). That is, secrets are available here as values
# of a specific set of 'well-known' environment variables. Not all of these
# configuration parameters are secrets, thought. Non-sensitive parameter names:
#
# CONBENCH_INTENDED_BASE_URL (scheme and DNS name)
# EKS_CLUSTER (the name of the EKS cluster to operate on)
# APPLICATION_NAME (shows up in the UI of the deployed web app)
# NAMESPACE (indicating the k8s namespace to deploy into)
# ...

build_and_push() {
  set -x
  make set-build-info
  docker build -t ${FLASK_APP} .
  docker tag ${FLASK_APP}:latest ${DOCKER_REGISTRY}/${FLASK_APP}:${BUILDKITE_COMMIT}
  aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin ${DOCKER_REGISTRY}
  docker push ${DOCKER_REGISTRY}/${FLASK_APP}:${BUILDKITE_COMMIT}
}

deploy_secrets_and_config() {

  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl config set-context --current --namespace=${NAMESPACE}

  if [ -z "$GOOGLE_CLIENT_ID" ]; then
      cat conbench-secret.yml | sed "\
        s/{{DB_PASSWORD}}/$(echo -n $DB_PASSWORD | base64)/g;\
        s/{{DB_USERNAME}}/$(echo -n $DB_USERNAME | base64)/g;\
        s/{{GITHUB_API_TOKEN}}/$(echo -n $GITHUB_API_TOKEN | base64)/g;\
        s/GOOGLE_CLIENT_ID: {{GOOGLE_CLIENT_ID}}//g;\
        s/GOOGLE_CLIENT_SECRET: {{GOOGLE_CLIENT_SECRET}}//g;\
        s/{{REGISTRATION_KEY}}/$(echo -n $REGISTRATION_KEY | base64)/g;\
        s/{{SECRET_KEY}}/$(echo -n $SECRET_KEY | base64)/g" |
    kubectl apply -f -
  else
    cat conbench-secret.yml | sed "\
        s/{{DB_PASSWORD}}/$(echo -n $DB_PASSWORD | base64)/g;\
        s/{{DB_USERNAME}}/$(echo -n $DB_USERNAME | base64)/g;\
        s/{{GITHUB_API_TOKEN}}/$(echo -n $GITHUB_API_TOKEN | base64)/g;\
        s/{{GOOGLE_CLIENT_ID}}/$(echo -n $GOOGLE_CLIENT_ID | base64 -w 0)/g;\
        s/{{GOOGLE_CLIENT_SECRET}}/$(echo -n $GOOGLE_CLIENT_SECRET | base64)/g;\
        s/{{REGISTRATION_KEY}}/$(echo -n $REGISTRATION_KEY | base64)/g;\
        s/{{SECRET_KEY}}/$(echo -n $SECRET_KEY | base64)/g" |
    kubectl apply -f -

  fi

  cat conbench-config.yml | sed "\
        s|{{CONBENCH_INTENDED_BASE_URL}}|${CONBENCH_INTENDED_BASE_URL}|g; \
        s/{{APPLICATION_NAME}}/${APPLICATION_NAME}/g;\
        s/{{BENCHMARKS_DATA_PUBLIC}}/${BENCHMARKS_DATA_PUBLIC}/g;\
        s/{{DB_NAME}}/${DB_NAME}/g;\
        s/{{DB_HOST}}/${DB_HOST}/g;\
        s/{{DB_PORT}}/${DB_PORT}/g;\
        s/{{FLASK_APP}}/${FLASK_APP}/g;\
        s/{{DISTRIBUTION_COMMITS}}/${DISTRIBUTION_COMMITS}/g; \
        s/{{BENCHMARKS_DATA_PUBLIC}}/${BENCHMARKS_DATA_PUBLIC}/g" | kubectl apply -f -
}

run_migrations() {
  set -x

  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl config set-context --current --namespace=${NAMESPACE}

  sed "s|{{CONBENCH_WEBAPP_IMAGE_SPEC}}|${IMAGE_SPEC}|g" \
    < k8s/conbench-db-migration.templ.yml \
    > _jobspec

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


  # Note(JP): This runs as part of a BK pipeline and uses AWS credentials that
  # have the `--group system:masters --username admin` privilege, see:
  # infra/blob/0a21e9a2eee1ea158d2a2a5d216407741feb3931/conbench/app/stacks/eks/main.tf#L80
  # EKS_CLUSTER is currently "vd-2" for cb&cb-staging.
  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}

  # All of the following kubectl commands operate on a definite namespace.
  # NAMESPACE is something like "default" or "staging"
  kubectl config set-context --current --namespace=${NAMESPACE}

  # (Re-)apply deployment. BUILDKITE_COMMIT is the Conbench repo commit.
  cat k8s/conbench-deployment.templ.yml | \
    sed "s|{{CONBENCH_WEBAPP_IMAGE_SPEC}}|${IMAGE_SPEC}|g" | kubectl apply -f -

  # (Re-)apply ALB ingress config. Note(JP): if this results in re-creation of
  # the ALB then we need to out-of-band update an A record in Route53, because
  # we do not yet use k8s externalDNS features.
  cat k8s/conbench-cloud-ingress.templ.yml | \
    sed "s/{{CERTIFICATE_ARN}}/${CERTIFICATE_ARN}/g" | kubectl apply -f -

  kubectl apply -f k8s/conbench-service.yml
  kubectl apply -f k8s/conbench-service-monitor.yml

  # Note(JP); this might be nonobvious, but `rollout status` waits for
  # progressDeadlineSeconds (see deployment manifast) before it exits non-zero.
  # See
  # https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#failed-deployment
  kubectl rollout status deployment/conbench-deployment

  # Towards https://github.com/conbench/conbench/issues/993.
  # The current working directory, I hope, is the Conbench checkout.
  make jsonnet-kube-prom-manifests || echo "ouch, but ignore for now"

  # Note(JP): let's do a bit of magic. In the special case of working against
  # vd-2 (specific EKS cluster in a specific AWS account, powering two specific
  # Conbench deployments): install the conbench-flavored kube-prometheus stack,
  # or update it. Updates may be as tiny as rolling out Grafana dashboard
  # changes. I really do hope that this works (that it is OK to run this even N
  # times per day against the same k8s cluster), because this will be fantastic
  # in terms of developer productivity. The comments in
  # k8s/kube-prometheus/deploy-or-update.sh explain relevant concepts. Notably,
  # `k8s/kube-prometheus/deploy-or-update.sh` itself is tested in Conbench repo
  # CI as part of the minikube flow.
  set +x
  if [[ "$EKS_CLUSTER" == "vd-2" ]]; then
    echo "vd-2: run k8s/kube-prometheus/deploy-or-update.sh, and pray that this does not impede the robustness of our deploy pipeline"
    export CONBENCH_REPO_ROOT_DIR="$(pwd)"
    bash k8s/kube-prometheus/deploy-or-update.sh
  fi
}

rollback() {
  set -x
  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl config set-context --current --namespace=${NAMESPACE}
  kubectl rollout undo deployment.v1.apps/conbench-deployment
  kubectl rollout status deployment/conbench-deployment
}

# why is this here? hm :).
"$@"
