FROM python:3.8

COPY requirements-build.txt /tmp/
COPY requirements-test.txt /tmp/
RUN pip install -r /tmp/requirements-build.txt
RUN pip install -r /tmp/requirements-test.txt

WORKDIR /app
ADD . /app
