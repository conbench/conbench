# Note(JP): we will have to figure out which of these targets will transition
# to be 'public interface', i.e. used by developers. Those should only
# conservatively be changed (in terms of naming and behavior). Other Makefile
# targets might be considered 'private interface', to make things in CI simpler
# -- those targets can change at will, often and brutally (their names, their
# meaning, and their implementation)

# This is used by CI for running the test suite. Documentation should encourage
# developers to run this command locally, too.
.PHONY: tests
tests:
	docker compose down --remove-orphans && \
	docker compose build app && \
	docker compose run \
	-e COVERAGE_FILE=/etc/conbench-coverage-dir/.coverage \
	-e CI=true \
	app \
	coverage run --source conbench \
		-m pytest -vv -s --durations=20 conbench/tests/


# For developers, these commands may and should modify local files if possible.
.PHONY: lint
lint:
	flake8
	isort .
	black --diff .


# Run by CI, these commands should not modify files, but only check compliance.
.PHONY: lint-ci
lint-ci:
	flake8
	isort --check .
	black --check --diff .


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
	git diff ./conbench/tests/api/_expected_docs.py


.PHONY: run-app
run-app:
	export DCOMP_CONBENCH_HOST_PORT=127.0.0.1:5000 && \
		docker compose down && docker compose up --build


.PHONY: run-app-bg
run-app-bg:
	docker compose up --build --wait --detach

.PHONY: stop-app-bg
stop-app-bg:
	docker compose down
