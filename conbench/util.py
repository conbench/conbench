import importlib.util
import json
import os
import sys
import urllib.parse
import yaml

import click
import requests

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


retry_strategy = Retry(
    total=5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST"]),
    backoff_factor=4,  # will retry in 2, 4, 8, 16, 32 seconds
)
adapter = HTTPAdapter(max_retries=retry_strategy)


class Connection:
    def __init__(self):
        self.config = Config(get_config())
        self.session = None

    def publish(self, benchmark):
        self.post(self.config.benchmarks_url, benchmark)

    def compare_benchmarks(self, baseline_id, contender_id, threshold):
        compare_url = self.config.compare_benchmarks_url(
            baseline_id, contender_id, threshold
        )
        return self.get(compare_url)

    def compare_batches(self, baseline_id, contender_id, threshold):
        compare_url = self.config.compare_batches_url(
            baseline_id, contender_id, threshold
        )
        return self.get(compare_url)

    def compare_runs(self, baseline_id, contender_id, threshold):
        compare_url = self.config.compare_runs_url(baseline_id, contender_id, threshold)
        return self.get(compare_url)

    def post(self, url, data):
        if self.session:
            # already authenticated, just do post
            self._post(url, data, 201)

        if not self.session:
            # not already authenticated, or authentication expired (try again)
            self._post(self.config.login_url, self.config.credentials, 204)
            self._post(url, data, 201)

    def get(self, url):
        if self.session:
            # already authenticated, just do get
            response = self._get(url, 200)

        if not self.session:
            # not already authenticated, or authentication expired (try again)
            self._post(self.config.login_url, self.config.credentials, 204)
            response = self._get(url, 200)

        return response

    def _post(self, url, data, expected):
        try:
            if not self.session:
                self.session = requests.Session()
                self.session.mount("https://", adapter)
            response = self.session.post(url, json=data)
            if response.status_code != expected:
                self._unexpected_response("POST", response, url)
        except requests.exceptions.ConnectionError:
            self.session = None

    def _get(self, url, expected):
        result = None

        try:
            if not self.session:
                self.session = requests.Session()
                self.session.mount("https://", adapter)
            response = self.session.get(url)
            if response.status_code != expected:
                self._unexpected_response("GET", response, url)
            else:
                result = json.loads(response.content)
        except requests.exceptions.ConnectionError:
            self.session = None

        return result

    def _unexpected_response(self, method, response, url):
        self._print_error(f"\n{method} {url} failed", red=True)
        message = json.loads(response.content)
        if response.content:
            self._print_error(f"{json.dumps(message, indent=2)}\n")
        self.session = None

    def _print_error(self, msg, red=False):
        if red:
            click.echo(click.style(msg, fg="red"))
        else:
            click.echo(msg)


class Config:
    def __init__(self, config):
        url = config.get("url", "http://localhost:5000")
        email = config.get("email", "conbench@example.com")
        password = config.get("password", "conbench")
        self.login_url = urllib.parse.urljoin(url, "api/login/")
        self.benchmarks_url = urllib.parse.urljoin(url, "api/benchmarks/")
        self.compare_url = urllib.parse.urljoin(url, "api/compare/")
        self.credentials = {"email": email, "password": password}

    def compare_benchmarks_url(self, baseline_id, contender_id, threshold):
        compare = f"{contender_id}...{baseline_id}"
        return f"{self.compare_url}benchmarks/{compare}/?threshold={threshold}"

    def compare_batches_url(self, baseline_id, contender_id, threshold):
        compare = f"{contender_id}...{baseline_id}"
        return f"{self.compare_url}batches/{compare}/?threshold={threshold}"

    def compare_runs_url(self, baseline_id, contender_id, threshold):
        compare = f"{contender_id}...{baseline_id}"
        return f"{self.compare_url}runs/{compare}/?threshold={threshold}"


def get_config(filename=None):
    """Get config from a yaml file named .conbench in the current
    working directory.
    """
    if filename is None:
        filename = ".conbench"
    current_dir = os.getcwd()
    file_path = os.path.join(current_dir, filename)
    try:
        with open(file_path) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError:
        config = {}
    return config


def register_benchmarks(directory=None):
    """Look for files matching the following patterns in the current
    working directory and import them.

        bench_*.py
        benchmark_*.py
        *_bench.py
        *_benchmark.py
        *_benchmarks.py

    This registers benchmarks that are decorated as conbench benchmarks.

        import conbench.runner

        @conbench.runner.register_benchmark
        class ExampleBenchmark():
            name = "example"
    """
    if directory is None:
        directory = os.getcwd()
    with os.scandir(directory) as scan:
        for entry in scan:
            filename = entry.name
            if (
                filename.startswith(".")
                or not entry.is_file()
                or not filename.endswith(".py")
            ):
                continue
            if (
                filename.startswith("bench_")
                or filename.startswith("benchmark_")
                or filename.endswith("_bench.py")
                or filename.endswith("_benchmark.py")
                or filename.endswith("_benchmarks.py")
            ):
                import_module(directory, filename)


def import_module(directory, filename):
    module_name = filename.split(".")[0]
    file_path = os.path.join(directory, filename)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
