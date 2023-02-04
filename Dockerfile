FROM python:3.11-slim

# curl is needed for docker-compose health checks. `git` is needed by some unit
# tests as of today.
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    curl git && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements-webapp.txt /tmp/
COPY requirements-dev.txt /tmp/

RUN pip install -r /tmp/requirements-webapp.txt && \
    pip install -r /tmp/requirements-dev.txt && \
    rm -rf ./root/.cache

# This Dockerfile currently defines the image used for production environments.
# It also contains all test dependencies and most CI dependencies because it's
# currently also being used to run CI tasks. For production, it's important
# that the `app` directory is baked in, containing current Conbench code. For
# local development, /app may be overridden to be a volume-mount.
WORKDIR /app

# Only copy in the files that are required (instead of the entire repo root),
# to make more use of Docker container image layer caching.
COPY conbench /app/conbench
COPY migrations /app/migrations

# TODO: make it so that .git is not needed
# see https://github.com/conbench/conbench/pull/667
COPY .git /app/.git
COPY setup.py README.md requirements-cli.txt requirements-webapp.txt requirements-dev.txt alembic.ini /app/

# Inspect contents of /app
RUN pwd && /bin/ls -1 .

# Installing this package as of now is necessary not for installing
# dependencies, but for preventing:
# importlib.metadata.PackageNotFoundError: No package metadata was found for conbench
RUN pip install .

# Make it so that this directory exists in the container file system. That's
# the value of the PROMETHEUS_MULTIPROC_DIR env var. The prometheus-client
# Python library needs this to be set to a path pointing to a directory. I have
# tried setting this up within the CPython process (early during import) but
# that wasn't early enough. Note that when mounting the host's /tmp to the
# container's /tmp the host is expected to have /tmp/_conbench-promcl-coord-dir
# in its file system.
RUN mkdir -p /tmp/_conbench-promcl-coord-dir


# Re-active this to get ideas for how the image size can be further reduced.
#RUN echo "biggest dirs"
#RUN cd / && du -ha . | sort -r -h | head -n 50 || true
