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
tests: require-env-ghtoken
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
