FROM python:3.11-slim

# Curl is needed for docker-compose health checks.
RUN apk add --update curl &&  rm -rf /var/cache/apk/*

COPY requirements-webapp.txt /tmp/
COPY requirements-dev.txt /tmp/

# Delete pip cache in same image layer.
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
# to make most use of Docker container image layer caching.
COPY conbench /app/conbench
COPY migrations /app/migrations
COPY setup.py README.md requirements-cli.txt requirements-webapp.txt requirements-dev.txt alembic.ini /app/

# Inspect contents of /app
RUN pwd && /bin/ls -1 .

# Installing this package as of now is necessary not for installing
# dependencies, but for preventing:
# Answer: otherwise this happens:
# importlib.metadata.PackageNotFoundError: No package metadata was found for conbench
RUN pip install .

#RUN echo "biggest dirs"
#RUN cd / && du -ha . | sort -r -h | head -n 50 || true

