#!/bin/bash

build_and_push() {
  set -x
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
        s/{{APPLICATION_NAME}}/${APPLICATION_NAME}/g;\
        s/{{BENCHMARKS_DATA_PUBLIC}}/${BENCHMARKS_DATA_PUBLIC}/g;\
        s/{{DB_NAME}}/${DB_NAME}/g;\
        s/{{DB_HOST}}/${DB_HOST}/g;\
        s/{{DB_PORT}}/${DB_PORT}/g;\
        s/{{FLASK_APP}}/${FLASK_APP}/g;\
        s/{{BENCHMARKS_DATA_PUBLIC}}/${BENCHMARKS_DATA_PUBLIC}/g" | kubectl apply -f -
}

run_migrations() {
  set -x
  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl config set-context --current --namespace=${NAMESPACE}
  cat migration-job.yml | sed "\
        s/{{BUILDKITE_COMMIT}}/${BUILDKITE_COMMIT}/g;\
        s/{{DOCKER_REGISTRY}}/${DOCKER_REGISTRY}/g;\
        s/{{FLASK_APP}}/${FLASK_APP}/g" |
    kubectl delete --ignore-not-found=true -f -
  cat migration-job.yml | sed "\
        s/{{BUILDKITE_COMMIT}}/${BUILDKITE_COMMIT}/g;\
        s/{{DOCKER_REGISTRY}}/${DOCKER_REGISTRY}/g;\
        s/{{FLASK_APP}}/${FLASK_APP}/g" |
    kubectl apply -f -
  kubectl wait --for=condition=complete --timeout=259200s job/conbench-migration
  (($(kubectl get job conbench-migration -o jsonpath={.status.succeeded}) == "1")) && exit 0 || exit 1
}

deploy() {
  set -x
  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl config set-context --current --namespace=${NAMESPACE}
  cat deploy.yml | sed "\
s/{{BUILDKITE_COMMIT}}/${BUILDKITE_COMMIT}/g;\
        s/{{CERTIFICATE_ARN}}/${CERTIFICATE_ARN}/g;\
        s/{{DOCKER_REGISTRY}}/${DOCKER_REGISTRY}/g;\
        s/{{FLASK_APP}}/${FLASK_APP}/g" |
    kubectl apply -f -
  kubectl rollout status deployment/conbench-deployment
}

upload_conbench_to_pypi() {
  last_released_version=$(curl https://pypi.org/pypi/conbench/json | jq '.info.version' | tr -d '"')
  version=$(grep version= setup.py | tr -d '"' | tr -d 'version=' | tr -d ',' | tr -d ' ')

  echo Last conbench version released to PyPI: $last_released_version
  echo Current conbench project version: $version

  if [[ $last_released_version < $version ]]; then
    echo "Releasing new conbench version"
  else
    echo "Conbench version " $version " is already released to PyPI"
    return
  fi

  eval "$(command '/opt/conda/condabin/conda' 'shell.bash' 'hook' 2> /dev/null)"
  conda create -y -n conbench --force -c conda-forge python=3.8
  conda activate conbench
  pip install -r requirements-test.txt -r requirements-build.txt -r requirements-cli.txt
  pip install -e .
  python -m pip install --upgrade build
  python -m pip install --upgrade twine
  rm -rf dist
  python -m build
  python -m twine upload dist/*
}

rollback() {
  set -x
  aws eks --region us-east-2 update-kubeconfig --name ${EKS_CLUSTER}
  kubectl rollout undo deployment.v1.apps/conbench-deployment
  kubectl rollout status deployment/conbench-deployment
}

"$@"
