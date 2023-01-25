FROM python:3.11

COPY requirements-webapp.txt /tmp/
COPY requirements-dev.txt /tmp/
RUN pip install -r /tmp/requirements-webapp.txt
RUN pip install -r /tmp/requirements-dev.txt

# This Dockerfile currently defines the image used for production environments.
# It also contains all test dependencies and most CI dependencies because it's
# currently also being used to run CI tasks. For production, it's important
# that the `app` directory is baked in, containing current Conbench code. For
# local development, /app may be overridden to be a volume-mount.
WORKDIR /app
ADD . /app
RUN pip install .
