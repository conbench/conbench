


.PHONY: tests
tests:
	docker-compose down && \
	docker-compose build app && \
	docker-compose run \
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


