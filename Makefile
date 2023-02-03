# Note(JP): we will have to figure out which of these targets will transition
# to be 'public interface', i.e. used by developers. Those should only
# conservatively be changed (in terms of naming and behavior). Other Makefile
# targets might be considered 'private interface', to make things in CI simpler
# -- those targets can change at will, often and brutally (their names, their
# meaning, and their implementation)

# The use case that this target mainly has in mind: starting the application
# locally to play around with this. This is not primarily meant for
# _development_.
.PHONY: run-app
run-app:
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
tests:
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
run-app-dev:
	export DCOMP_CONBENCH_METRICS_HOST_PORT=127.0.0.1:8000 && \
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


# Run by CI, these commands should not modify files, but only check compliance.
.PHONY: lint-ci
lint-ci:
	flake8
	isort --check .
	black --check --diff .
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


.PHONY: run-app-bg
run-app-bg:
	docker compose up --build --wait --detach


# This is here for the purpose of testing most of `run-app-dev` in CI. A copy
# of `run-app-dev` but not requiring a specific port on the host, and using
# --wait and --detach. That means that `docker compose up...` will return with
# exit code 0 once the app appears to be healthy. At this point we can run the
# teardown which is also expected to return with code 0. If the `up` command
# fails then emit container logs before fast-failing the makefile target.
.PHONY: test-run-app-dev
test-run-app-dev:
	docker compose down
	docker compose -f docker-compose.yml -f docker-compose.dev.yml \
		up --build --wait --detach || (docker compose logs --since 30m; exit 1)
	docker compose down

# The version string representing the current checkout / working directory.
# This for example defines the Docker image tags. The default `dev` suffix
# represents a local dev environment. Override CHECKOUT_VERSION_STRING with a
# different suffix (e.g. `ci`) in the CI environment so that the version string
# attached to build artifacts reveals the environment that the build artifact
# was created in.
export CHECKOUT_VERSION_STRING ?= $(shell git rev-parse --short=9 HEAD)-dev
# Set a different repo organization for pushing images to
DOCKER_REPO ?= conbench

CONTAINER_IMAGE_SPEC=$(DOCKER_REPO)/conbench:$(CHECKOUT_VERSION_STRING)

$(info --------------------------------------------------------------)
$(info CONTAINER_IMAGE_SPEC is $(CONTAINER_IMAGE_SPEC))
$(info --------------------------------------------------------------)


.PHONY: build-conbench-container-image
build-conbench-container-image:
	docker build . -f Dockerfile -t ${CONTAINER_IMAGE_SPEC}
	echo "Size of docker image:"
	docker images --format "{{.Size}}" ${CONTAINER_IMAGE_SPEC}
	# docker push ${CONTAINER_IMAGE_SPEC}


# The `minikube image load` technique is rather new and allows for using local
# Docker images in k8s deployments (as long as they specify `imagePullPolicy:
# Never`). That command however takes a while for bigger images (about 1 min
# per GB, on my machine).
# https://minikube.sigs.k8s.io/docs/handbook/pushing/
# https://stackoverflow.com/a/62303945
.PHONY: deploy-on-minikube
deploy-on-minikube:
	minikube status
	mkdir -p _build
	cat ci/minikube/deploy-conbench.template.yml > _build/deploy-conbench.yml
	sed -i.bak "s|<CONBENCH_CONTAINER_IMAGE_SPEC>|${CONTAINER_IMAGE_SPEC}|g" _build/deploy-conbench.yml
	rm _build/deploy-conbench.yml.bak
	time minikube image load ${CONTAINER_IMAGE_SPEC}
	minikube kubectl -- apply -f  _build/deploy-conbench.yml

