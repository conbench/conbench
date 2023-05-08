# Specify platform so that developers using this on ARM MacOS get to use the
# same Python wheels (platform-specific binaries) that we use when running this
# on Linux. Otherwise, some wheels might not exist on PyPI (psutil) and
# compilation tools are required for building C extensions. Downside: when
# executing an AMD64 image on ARM the QEMU emulation layer inficts a small
# slowdown.
# Also see https://github.com/conbench/conbench/issues/709 and
# https://docs.docker.com/engine/reference/builder/#from
# https://www.docker.com/blog/multi-platform-docker-builds/
# FROM --platform=linux/amd64 python:3.11-slim
#
# Update: the slowdown may be not so small, see
# https://github.com/conbench/conbench/issues/914
# The downside here is that with `build-essential` baked into the image we
# do a bad job optimizing for image size; but we do that anyway so far, so
# maybe it's really not a big deal.
FROM python:3.11-slim-bullseye

# curl is needed for docker-compose health checks. `git` is needed by some unit
# tests as of today. build-essential is for non-binary wheels for aarch64
# developer platforms, like for psutil. libpq dev is for psycopg2 source build.
RUN apt-get update && apt-get install -y -q --no-install-recommends \
    curl git build-essential curl ca-certificates gnupg && \
    # Install postgres-client-15 from official PG repo
    # see https://wiki.postgresql.org/wiki/Apt -- I added `bullseye`
    # so that we do not need lsb_release
    curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
        gpg --dearmor | tee /etc/apt/trusted.gpg.d/apt.postgresql.org.gpg >/dev/null && \
        sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt bullseye-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
        apt update && apt install -y postgresql-client-15 libpq-dev  && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

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

# Bake build information into container image. This invalidates the layer
# cache for every commit and therefore it is important to do this as late as
# possible in this Dockerfile.
COPY ./buildinfo.json /buildinfo.json

# Re-active this to get ideas for how the image size can be further reduced.
#RUN echo "biggest dirs"
#RUN cd / && du -ha . | sort -r -h | head -n 50 || true

