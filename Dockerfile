FROM python:3.11

COPY requirements-build.txt /tmp/
COPY requirements-test.txt /tmp/
RUN pip install -r /tmp/requirements-build.txt
RUN pip install -r /tmp/requirements-test.txt

# This Dockerfile currently defines the image used for production environments.
# It also contains all test dependencies and most CI dependencies because it's
# currently also being used to run CI tasks. For production, it's important
# that the `app` directory is baked in, containing current Conbench code. For
# local development, /app may be overridden to be a volume-mount.
WORKDIR /app
ADD . /app
RUN pip install .
