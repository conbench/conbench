# Note(JP): we try to distinguish targets that are 'public interface' (i.e.
# commonly used by developers) from targets that are 'private interface' (used
# by CI, very rarely used by humans). 'public interface' targets should only
# conservatively be changed (with conscious iteration on naming and behavior).
# The other targets can change often and brutally (their names, their meaning,
# and their implementation).

# The use case that this target mainly has in mind: starting the application
# locally to play around with this. This is not primarily meant for
# _development_.
.PHONY: run-app
run-app: set-build-info
	export DCOMP_CONBENCH_HOST_PORT=127.0.0.1:5000 && \
		docker compose down && docker compose up --build


# This removes state by removing containers. That means that the next `make
# run-app` invocation will start with fresh container state.
.PHONY: teardown-app
teardown-app:
	docker compose down --remove-orphans


# This requries dependencies to be set up in host env
.PHONY: db-populate
db-populate:
	python conbench/tests/populate_local_conbench.py


# This is used by CI for running the test suite. Documentation should encourage
# developers to run this command locally, too.
.PHONY: tests
tests: require-env-ghtoken set-build-info
	docker compose down --remove-orphans && \
	docker compose build app && \
	docker compose run \
		-e COVERAGE_FILE=/etc/conbench-coverage-dir/.coverage \
		app \
		coverage run --source conbench \
			-m pytest -vv -s --durations=20 conbench/tests/


# Similar to `make run-app`, but with the `docker-compose.dev.yml` extension
# That mounts the local checkout into the Conbench container.
.PHONY: run-app-dev
run-app-dev: set-build-info
	rm -rf /tmp/_conbench-promcl-coord-dir && mkdir -p /tmp/_conbench-promcl-coord-dir
	export DCOMP_CONBENCH_HOST_PORT=127.0.0.1:5000 && \
		docker compose down && \
			docker compose -f docker-compose.yml -f docker-compose.dev.yml \
				up --build


# For developers, these commands may and should modify local files if possible.
# This requires the dependencies to be available on the host, in the terminal
# that this target is executed in.
.PHONY: lint
lint:
	flake8
	isort .
	black .
	mypy conbench


.PHONY: rebuild-expected-api-docs
rebuild-expected-api-docs: run-app-bg
	echo "using $(shell docker compose port app 5000) to reach app"
	curl --silent --show-error --fail --retry 10 \
		--retry-all-errors --retry-delay 1 --retry-max-time 30 \
			http://$(shell docker compose port app 5000)/api/docs.json > _new_api_docs.json
	docker compose down
	python -c "import json; print(str(json.loads(open('_new_api_docs.json').read())))" > _new_api_docs.py
	black _new_api_docs.py
	mv -f _new_api_docs.py ./conbench/tests/api/_expected_docs.py
	rm _new_api_docs.json
	git diff ./conbench/tests/api/_expected_docs.py

# The targets above this comment have been in use by humans. Change
# conservatively.


# Run by CI, these commands should not modify files, but only check compliance.
.PHONY: lint-ci
lint-ci:
	flake8
	isort --check .
	black --check --diff .
	mypy conbench


require-env-ghtoken:
ifndef GITHUB_API_TOKEN
	$(error the environment variable GITHUB_API_TOKEN must be set)
endif


.PHONY: run-app-bg
run-app-bg: set-build-info
	docker compose up --build --wait --detach


# This is here for the purpose of testing most of `run-app-dev` in CI. A copy
# of `run-app-dev` but not requiring a specific port on the host, and using
# --wait and --detach. That means that `docker compose up...` will return with
# exit code 0 once the app appears to be healthy. At this point we can run the
# teardown which is also expected to return with code 0. If the `up` command
# fails then emit container logs before fast-failing the makefile target.
.PHONY: test-run-app-dev
test-run-app-dev: set-build-info
	mkdir -p /tmp/_conbench-promcl-coord-dir
	docker compose down --remove-orphans
	docker compose -f docker-compose.yml -f docker-compose.dev.yml \
		up --build --wait --detach || (docker compose logs --since 30m; exit 1)
	docker compose down


# The version string representing the current checkout / working directory. The
# default `dev` suffix represents a local dev environment. Override
# CHECKOUT_VERSION_STRING with a different suffix (e.g. `ci`) in the CI
# environment so that the version string attached to build artifacts reveals
# the environment that the build artifact was created in.
export CHECKOUT_VERSION_STRING ?= $(shell git rev-parse --short=9 HEAD)-dev
DOCKER_REPO_ORG ?= conbench
CONTAINER_IMAGE_SPEC=$(DOCKER_REPO_ORG)/conbench:$(CHECKOUT_VERSION_STRING)


.PHONY: build-conbench-container-image
build-conbench-container-image: set-build-info
	docker build . -f Dockerfile -t ${CONTAINER_IMAGE_SPEC}
	echo "Size of docker image:"
	docker images --format "{{.Size}}" ${CONTAINER_IMAGE_SPEC}
	# docker push ${CONTAINER_IMAGE_SPEC}


# On GHA, the default minikube profile name is used, cannot be overridden yet
# (see https://github.com/medyagh/setup-minikube/issues/59). Locally, we use a
# specific profile name though. Note that this target here is invoked in the
# context of ci/minikube/test-conbench-on-mk.sh. That wrapper is expected to set  The `minikube image load`
# technique allows for using local Docker images in k8s deployments (as long as
# they specify `imagePullPolicy: Never`). That command however takes a while
# for bigger images (about 1 min per GB, on my machine).
# https://minikube.sigs.k8s.io/docs/handbook/pushing/
# https://stackoverflow.com/a/62303945
.PHONY: deploy-on-minikube
deploy-on-minikube:
	minikube status || minikube status --profile mk-conbench
	mkdir -p _build
	cp ci/minikube/deploy-conbench.template.yml _build/deploy-conbench.yml
	sed -i.bak "s|<CONBENCH_CONTAINER_IMAGE_SPEC>|${CONTAINER_IMAGE_SPEC}|g" _build/deploy-conbench.yml
	time minikube --profile "${MINIKUBE_PROFILE_NAME}" image load ${CONTAINER_IMAGE_SPEC}
	minikube --profile "${MINIKUBE_PROFILE_NAME}" kubectl -- apply -f _build/deploy-conbench.yml


# Thin wrapper currently not covered by CI. But the core
# (../ci/minikube/test-conbench-on-mk.sh) is covered.
.PHONY: conbench-on-minikube
conbench-on-minikube: build-conbench-container-image start-minikube
	rm -rf _build && mkdir -p _build && cd _build && bash ../ci/minikube/test-conbench-on-mk.sh
	@echo "run: kubectl --namespace monitoring port-forward svc/grafana 3000"
	@echo "then open the Grafana UI at: http://localhost:3000 "
	@echo "log in with admin/admin"
	@echo "run: kubectl port-forward svc/conbench-service 8000:conbench-service-port"
	@echo "then open the Conbench UI at: http://localhost:8000 "


# Currently not covered by CI. This is for now only meant for local dev
# machines (in GHA we use a special action to launch minikube). Use a specific
# minikube profile name to not act on potentially other minikube VMs that are
# running on the host. Some of the cmdline flags are taken from
# https://github.com/prometheus-operator/kube-prometheus#minikube
# https://minikube.sigs.k8s.io/docs/commands/start/
.PHONY: start-minikube
start-minikube:
	minikube delete --profile mk-conbench
	minikube start --profile mk-conbench --cpus=2 --memory=4g \
		--disable-metrics \
		--kubernetes-version=v1.24.10 \
		--bootstrapper=kubeadm \
		--extra-config=kubelet.authentication-token-webhook=true \
		--extra-config=kubelet.authorization-mode=Webhook \
		--extra-config=scheduler.bind-address=0.0.0.0 \
		--extra-config=controller-manager.bind-address=0.0.0.0


.PHONY: set-build-info
set-build-info:
	# Write a file buildinfo.json to the root of the repository. This file is
	# later meant to be added to build artifacts / container images. For
	# discovery during runtime (via convention on the path in the container
	# file system). During non-containerized local dev, either do not fail when
	# this file does not exist or use path convention on host file system or
	# introduce an environment variable (sth like CONBENCH_BUILDINFO_PATH).
	#
	# Use `sed` for the replacements below. Exit code is 0 for both cases:
	# replacement made, or replacement not made. Expect non-zero exit code only
	# for e.g. file not existing.
	#
	# Notes:
	# - `buildinfo.json` is not tracked in the repository.
	# - `git branch --show-current` requires at least git 2.22.
	# - use GITHUB_REF_NAME in GHA, documented with "The short ref name of the
	#   branch or tag that triggered the workflow run. This value matches the
	#   branch or tag name shown on GitHub"
	# - use in-place editing with `sed` to make this portable across Linux and
	#   macOS: https://stackoverflow.com/a/16746032/145400
	cat ci/buildinfo.json.template > buildinfo.json
	_GITBRANCH="$$(git branch --show-current)" || true; BRANCH_NAME=$${GITHUB_REF_NAME:-$$_GITBRANCH} && \
	sed -i.bak "s|<BUILD_INFO_BRANCH_NAME>|$${BRANCH_NAME}|g" \
		buildinfo.json
	sed -i.bak "s|<BUILD_INFO_VERSION_STRING>|${CHECKOUT_VERSION_STRING}|g" \
		buildinfo.json
	sed -i.bak "s|<BUILD_INFO_COMMIT>|$$(git rev-parse --verify HEAD)|g" \
		buildinfo.json
	sed -i.bak "s|<BUILD_INFO_TIME_RFC3339>|$$(date --utc +"%Y-%m-%d %H:%M:%SZ")|g" \
		buildinfo.json
	sed -i.bak "s|<BUILD_INFO_HOSTNAME>|$$(hostname)|g" \
		buildinfo.json
	rm buildinfo.json.bak
	echo "(re)generated buildinfo.json"
	cat buildinfo.json


# This uses JSONNET build tooling to rebuild all kube-prometheus manifest YAML
# files based on the file `conbench-flavor.jsonnet` (i.e, including
# conbench-specific customizations). It took me a longish while to get this
# working (and to briefly understand the JSONNET build chain). This method here
# is what we currently use for kube-prometheus customization. Note that the
# coreos/jsonnet-ci container image used below comes with `jq` (one could
# install this locally with e.g. sudo dnf install jsonnet) and also with
# gojsontoyaml (which is where I resorted to looking for a container image that
# has all dependencies baked in).
.PHONY: jsonnet-kube-prom-manifests
jsonnet-kube-prom-manifests:
#	rm -rf _kpbuild
	mkdir -p _kpbuild && cd _kpbuild  && mkdir -p cb-kube-prometheus
	cd _kpbuild/cb-kube-prometheus && \
		docker run --user $$(id -u):$$(id -g) --rm -v $$(pwd):$$(pwd) --workdir $$(pwd) quay.io/coreos/jsonnet-ci \
			jb init || echo "exists"
	cd _kpbuild/cb-kube-prometheus && \
		time docker run --user $$(id -u):$$(id -g) --rm -v $$(pwd):$$(pwd) --workdir $$(pwd) quay.io/coreos/jsonnet-ci \
			jb install github.com/prometheus-operator/kube-prometheus/jsonnet/kube-prometheus@v0.12.0
	cd _kpbuild/cb-kube-prometheus && \
		wget https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/v0.12.0/build.sh -O build.sh
	cp k8s/kube-prometheus/conbench-flavor.jsonnet _kpbuild/cb-kube-prometheus
	cp k8s/kube-prometheus/conbench-grafana-dashboard.json _kpbuild/cb-kube-prometheus
	cd _kpbuild/cb-kube-prometheus && \
		time docker run --user $$(id -u):$$(id -g) --rm -v $$(pwd):$$(pwd) --workdir $$(pwd) quay.io/coreos/jsonnet-ci \
			bash build.sh conbench-flavor.jsonnet
	echo "compiled manifest files: _kpbuild/cb-kube-prometheus/manifests"
