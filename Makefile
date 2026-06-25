# Conbench: Go backend + Svelte SPA + generated SDKs.
#
# The legacy Flask/Python application and old Python client packages are deleted
# from the maintained implementation. Active developer and CI targets below use
# the Go server, embedded SPA, generated clients, and Zensical docs.

# Build the public documentation site locally. Zensical reads zensical.toml and
# writes the static site to ./site by default. The version is pinned in
# requirements-docs.txt and reused by CI.
ZENSICAL_VERSION := $(shell sed -n 's/^zensical==//p' requirements-docs.txt)
ZENSICAL ?= uvx --from zensical==$(ZENSICAL_VERSION) zensical

.PHONY: check-zensical-version
check-zensical-version:
	@test -n "$(ZENSICAL_VERSION)" || { echo 'requirements-docs.txt must pin zensical with zensical==<version>'; exit 1; }
	@actual="$$( $(ZENSICAL) --version )"; \
	if [ "$$actual" != "$(ZENSICAL_VERSION)" ]; then \
		echo "expected zensical $(ZENSICAL_VERSION), got $$actual"; \
		exit 1; \
	fi

.PHONY: docs-link-check
docs-link-check:
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_docs_links
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_docs_rendered_assets
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/docs_links.py

.PHONY: build-docs
build-docs: check-zensical-version docs-link-check docs-screenshots-check
	$(ZENSICAL) build
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/docs_rendered_assets.py docs/site/assets site/assets
	echo 'To see the generated docs, open site/index.html'

.PHONY: docs-serve
docs-serve: check-zensical-version
	$(ZENSICAL) serve

.PHONY: docs-screenshots
docs-screenshots:
	./scripts/capture_docs_screenshots.sh

.PHONY: docs-screenshots-check
docs-screenshots-check:
	bash ./scripts/check_docs_screenshots.sh

.PHONY: clean-local
clean-local:
	rm -rf bin site var .cache web/node_modules web/playwright-report web/test-results
	rm -rf sdk/python/build sdk/python/dist sdk/python/.venv sdk/python/*.egg-info
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" \) -prune -exec rm -rf {} +
	@if [ -d web/dist ]; then find web/dist -mindepth 1 ! -name .gitkeep -exec rm -rf {} +; fi
	@if command -v go >/dev/null 2>&1; then go clean -cache; fi
	echo 'clean-local: removed generated local artifacts'


# The version string representing the current checkout / working directory. The
# default `dev` suffix represents a local dev environment. Override
# CHECKOUT_VERSION_STRING with a different suffix (e.g. `ci`) in the CI
# environment so that the version string attached to build artifacts reveals
# the environment that the build artifact was created in.
export CHECKOUT_VERSION_STRING ?= $(shell git rev-parse --short=9 HEAD)-dev
DOCKER_REPO_ORG ?= conbench
CONTAINER_IMAGE_SPEC=$(DOCKER_REPO_ORG)/conbench:$(CHECKOUT_VERSION_STRING)


.PHONY: build-conbench-container-image
build-conbench-container-image:
	docker build . -f Dockerfile.server -t ${CONTAINER_IMAGE_SPEC}
	echo "Size of docker image:"
	docker images --format "{{.Size}}" ${CONTAINER_IMAGE_SPEC}
	# docker push ${CONTAINER_IMAGE_SPEC}


# Regenerate internal/db/schema.sql from the Alembic migrations (the sqlc input).
# Alembic is the temporary schema source of truth; see docs/site/operations.md
# and docs/site/storage-roadmap.md for the schema-ownership transition.
.PHONY: schema
schema:
	scripts/gen_schema.sh

# Temporary schema-authoring helper. Alembic remains the schema source of truth,
# so this target uses the schema-only Alembic image, not an app runtime path.
SCHEMA_COMPOSE := docker compose -p conbench_schema_authoring -f docker-compose.schema.yml

.PHONY: schema-new-migration
schema-new-migration:
	@set -e; \
	if [ -z "$${ALEMBIC_MIGRATION_NAME:-}" ]; then \
		echo "ALEMBIC_MIGRATION_NAME must be set to an expressive name"; \
		exit 1; \
	fi; \
	cleanup() { $(SCHEMA_COMPOSE) down -v --remove-orphans >/dev/null 2>&1 || true; }; \
	trap cleanup EXIT; \
	$(SCHEMA_COMPOSE) down -v --remove-orphans; \
	$(SCHEMA_COMPOSE) build schema; \
	$(SCHEMA_COMPOSE) up -d db; \
	CREATE_ALL_TABLES=false $(SCHEMA_COMPOSE) run --rm --no-deps -e CREATE_ALL_TABLES=false schema alembic upgrade head; \
	CREATE_ALL_TABLES=false $(SCHEMA_COMPOSE) run --rm --no-deps -e CREATE_ALL_TABLES=false schema alembic revision -m "$${ALEMBIC_MIGRATION_NAME}"
	@echo "A handwritten migration stub was generated in migrations/versions."

# Schema-drift gate (CI + local): fail if internal/db/schema.sql is stale.
.PHONY: schema-check
schema-check:
	scripts/check_schema_drift.sh

.PHONY: go-deploy-manifest-check
go-deploy-manifest-check:
	scripts/check_go_deploy_manifests.sh

.PHONY: repo-hygiene-check
repo-hygiene-check:
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_repo_hygiene
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/repo_hygiene.py .

.PHONY: workflow-shape-check
workflow-shape-check: repo-hygiene-check
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_retired_python_surfaces

# Bring up only the ephemeral dev Postgres for local work against the schema.
.PHONY: dev-db
dev-db:
	docker compose -p conbench_backend_dev -f docker-compose.backend-dev.yml up -d db

SERVER_COMPOSE := docker compose -p conbench_server -f docker-compose.server.yml
SERVER_CONTAINER_SMOKE_HOST_PORT ?= 127.0.0.1:18080
SERVER_CONTAINER_SMOKE_URL ?= http://127.0.0.1:18080

.PHONY: server-container-build
server-container-build:
	$(SERVER_COMPOSE) build server

.PHONY: server-container-up
server-container-up:
	$(SERVER_COMPOSE) up --build --wait --detach

.PHONY: server-container-down
server-container-down:
	$(SERVER_COMPOSE) down -v --remove-orphans

.PHONY: server-container-smoke
server-container-smoke:
	@set -e; \
	trap 'status=$$?; if [ $$status -ne 0 ]; then $(SERVER_COMPOSE) logs --since 30m; fi; $(SERVER_COMPOSE) down -v --remove-orphans >/dev/null 2>&1 || true; exit $$status' EXIT; \
	$(SERVER_COMPOSE) down -v --remove-orphans; \
	DCOMP_CONBENCH_SERVER_HOST_PORT="$(SERVER_CONTAINER_SMOKE_HOST_PORT)" $(SERVER_COMPOSE) up --build --wait --detach; \
	curl -fsS "$(SERVER_CONTAINER_SMOKE_URL)/api/ping" >/dev/null; \
	curl -fsS "$(SERVER_CONTAINER_SMOKE_URL)/metrics" | grep -F "conbench_up 1" >/dev/null; \
	curl -fsS "$(SERVER_CONTAINER_SMOKE_URL)/docs" >/dev/null; \
	curl -fsS "$(SERVER_CONTAINER_SMOKE_URL)/" >/dev/null

# Run the backend dev loop: persistent dev Postgres + conbench serve (applies
# the schema if missing, seeds deterministic demo data, serves the API). Ctrl-C
# stops the server; the db keeps running. Re-runnable.
.PHONY: dev
dev:
	scripts/dev.sh

# Stop the backend dev Postgres (add `-v` to also wipe the seeded data volume).
.PHONY: dev-down
dev-down:
	docker compose -p conbench_backend_dev -f docker-compose.backend-dev.yml down

# Regenerate the typed Go data layer from schema.sql + query/*.sql.
.PHONY: sqlc
sqlc:
	sqlc generate

# Generated-code drift gate (CI + local): fail if the sqlc output is stale.
.PHONY: sqlc-check
sqlc-check:
	sqlc diff

# Go backend tooling. These operate on the Go module (cmd/ + internal/).
# `go-lint` fixes in place; `go-lint-ci` is check-only.
.PHONY: go-fmt
go-fmt:
	gofmt -w cmd internal

.PHONY: go-lint
go-lint:
	golangci-lint run --fix ./...

.PHONY: go-lint-ci
go-lint-ci:
	golangci-lint run ./...

.PHONY: go-vet
go-vet:
	go vet ./...

# Full Go suite. Postgres-backed tests use testcontainers and skip when Docker
# is unavailable.
.PHONY: go-test
go-test:
	go test -shuffle=on ./...

# Fast Go tests: -short skips the Postgres-backed tests (no Docker needed).
.PHONY: go-test-short
go-test-short:
	go test -short -shuffle=on ./...

# Codegen pipeline: huma -> OpenAPI -> typed clients. The Go structs are the
# source of truth; scripts/openapi_emit.go emits the spec without compiling
# generated-client-dependent CLI commands, and
# api/openapi.yaml is the reviewed, checked-in contract artifact. Clients are
# generated FROM that artifact. api/openapi-3.0.yaml is a downgrade of the same
# document for generators without 3.1 support (oapi-codegen, for the Go client).
# `make codegen-check` regenerates everything and fails on any diff, proving the
# artifacts match the server and the clients match the artifacts.
CODEGEN_PATHS := api/openapi.yaml api/openapi-3.0.yaml web/src/lib/api sdk/python/conbench sdk/go/conbench/conbench.gen.go
OPENAPI_PYTHON_CLIENT_VERSION := 0.29.0
OAPI_CODEGEN_VERSION := v2.7.0

.PHONY: openapi
openapi:
	go run ./scripts/openapi_emit.go > api/openapi.yaml
	go run ./scripts/openapi_emit.go --downgrade > api/openapi-3.0.yaml

# TS client: openapi-typescript types + the typed openapi-fetch wrapper.
.PHONY: codegen-ts
codegen-ts:
	cd web && bun install --frozen-lockfile
	cd web && bun run codegen

# Python client: openapi-python-client generates conbench/ from the spec, then
# applies small hand-written migration helpers that share the public package.
.PHONY: codegen-py
codegen-py:
	RUFF_CACHE_DIR=$(CURDIR)/var/ruff-cache uvx openapi-python-client@$(OPENAPI_PYTHON_CLIENT_VERSION) generate \
		--path api/openapi.yaml --output-path sdk/python/conbench \
		--meta none --overwrite
	cp -R sdk/python/overlays/conbench/. sdk/python/conbench/

.PHONY: python-sdk-test
python-sdk-test:
	./scripts/check_python_sdk_tests.sh

.PHONY: python-sdk-package-check
python-sdk-package-check:
	PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_python_sdk_artifact_hygiene
	./scripts/check_python_sdk_package.sh

.PHONY: python-sdk-check
python-sdk-check: python-sdk-test python-sdk-package-check

.PHONY: migration-examples-test
migration-examples-test:
	./scripts/check_migration_examples.sh

# Go client: oapi-codegen generates sdk/go/conbench from the 3.0 downgrade (it
# does not support 3.1). The generated client pulls in github.com/oapi-codegen/
# runtime; run `go mod tidy` after changing the spec.
.PHONY: codegen-go
codegen-go:
	go run github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@$(OAPI_CODEGEN_VERSION) \
		-config sdk/go/conbench/oapi-codegen.yaml api/openapi-3.0.yaml

.PHONY: codegen
codegen: openapi codegen-ts codegen-py codegen-go

# Drift gate: regenerate the spec and all clients, then fail if anything in the
# codegen paths changed (modified or newly generated). Proves the artifact
# matches the server and the clients match the artifact.
.PHONY: codegen-check
codegen-check: codegen
	@if [ -n "$$(git status --porcelain -- $(CODEGEN_PATHS))" ]; then \
		echo "codegen drift: run 'make codegen' and commit the result:"; \
		git status --porcelain -- $(CODEGEN_PATHS); \
		exit 1; \
	fi
	@echo "codegen-check: clean"

# web-build compiles the SPA into web/dist with Bun. Vite empties web/dist on
# each build, deleting the tracked .gitkeep embed placeholder, so we restore it
# whether the build succeeds or fails -- a failed build would otherwise leave
# the placeholder deleted and break the Go embed until restored by hand. The
# build's exit status is preserved so a failed web build still fails the target.
.PHONY: web-build
web-build:
	cd web && bun install --frozen-lockfile
	cd web && bun run build; status=$$?; git -C "$(CURDIR)" checkout -- web/dist/.gitkeep; exit $$status

.PHONY: build
build: web-build
	go build -o bin/conbench ./cmd/conbench

# e2e runs the keystone end-to-end check: boots the built server + ephemeral
# seeded Postgres, submits via the CLI, and runs the Playwright + Python SDK
# checks. Opt-in and Docker-required (no graceful skip); CI placement is 5zh0.
.PHONY: e2e
e2e:
	./scripts/e2e.sh
