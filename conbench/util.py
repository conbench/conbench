import json
import logging
import os
import re
import textwrap
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Union, overload

import click
import requests
import yaml
from _pytest.pathlib import import_path
from requests.adapters import HTTPAdapter

try:
    from urllib3.util import Retry
except ImportError:
    # Legacy around times where requests had version 2.3 something.
    from requests.packages.urllib3.util.retry import Retry  # type: ignore[no-redef]

retry_strategy = Retry(
    total=5,
    status_forcelist=[502, 503, 504],
    allowed_methods=frozenset(["GET", "POST"]),
    backoff_factor=4,  # will retry in 2, 4, 8, 16, 32 seconds
)
adapter = HTTPAdapter(max_retries=retry_strategy)


log = logging.getLogger()


def short_commit_msg(msg: str):
    """
    Return a string of non-zero length, and with predictable maximum length.

    Substitute multiple whitespace characters with a single space. Overall,
    truncate at maxlen (see implementation).

    Substitute 40-char hash values with their shortened variant

    If the input is an emtpy string then emit a placeholder message.
    """
    # Deal with empty string scenario (not sure if data model allows that),
    # but it's better to have a definite place holder than putting an empty
    # string into e.g. HTML.
    if not msg:
        return "no-message"

    result = " ".join(msg.split())

    # Shorten what looks like a full-length commit hash.
    # Might want to use re-based replace, but shrug.
    for m in re.findall(r"\b[0-9a-f]{40}\b", result):
        result = result.replace(m, m[:7])

    # Maybe this does not need to be an argument to this function,
    # then we have consistency across entire code base.
    maxlen = 150

    if len(result) > maxlen:
        result = result[:maxlen] + "..."

    return result


def tznaive_dt_to_aware_iso8601_for_api(dt: datetime) -> str:
    """We store datetime objects in the database in columns that are configured
    to not track timezone information. By convention, each of those tz-naive
    datetime objects in the database is to be interpreted in UTC. Before
    emitting a stringified variant of such timestamp to an API user, serialize
    to a tz-aware ISO 8601 timestring, indicating UTC (Zulu) time, via adding
    the 'Z'.

    Example output: 2022-11-25T16:02:00Z

    Note(JP) on time resolution: ISO 8601 allows for fractions of seconds in
    various formats (3-9 digits). Timestamps in Conbench are not used for
    uniquely identifying entities. When we return ISO 8601 timestamps to HTTP
    API users we have to have an opinion about the fraction of the second to
    encode in the string. I think it's valuable to have a predictable
    fixed-width format with non-dynamic time precision. As far as I understand
    the value and use of timestamps returned by the API, I think we do not need
    to emit fractions of seconds. Therefore the `timespec="seconds"` below.
    This is currently documented and also tested, but can of course be changed.
    """
    if dt.tzinfo is not None:
        # Programming error, but don't crash.
        log.warning(
            "tznaive_dt_to_aware_iso8601_for_api() got tz-aware datetime obj: %s", dt
        )
        if dt.tzinfo == timezone.utc:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return dt.isoformat(sep="T", timespec="seconds")

    return dt.isoformat(sep="T", timespec="seconds") + "Z"


@overload
def tznaive_iso8601_to_tzaware_dt(input: str) -> datetime:
    ...


@overload
def tznaive_iso8601_to_tzaware_dt(input: List[str]) -> List[datetime]:
    ...


def tznaive_iso8601_to_tzaware_dt(input):
    """
    Convert time strings into datetime objects.

    If a list of strings is provided return a list of datetime objects.

    If a single string is provided return a single datetime object.

    Assume that each provided string is in ISO 8601 notation without timezone
    information, but that the time is meant to be interpreted in the UTC
    timezone.

    If an input string is tz-aware and encodes UTC (Zulu) time then this
    timezone is retained.

    An input string that is tz-aware and that encodes a timezone other than UTC
    is unexpected input, as of e.g. a programming error or unexpected legacy
    database state. We decided to log a warning message instead of crashing in
    that case (also, the indicated time gets interpreted in UTC, i.e. the
    original timezone information is ignored).

    Note: this was built with and tested for a value like 2022-03-03T19:48:06
    which in this example represents a commit timestamp (in UTC, additional
    knowledge).
    """

    def _convert(s: str):
        dt = datetime.fromisoformat(s)

        if dt.tzinfo == timezone.utc:
            return dt

        elif dt.tzinfo is not None:
            # Input seems to be tz-aware but the timezone it specifies does not
            # match UTC.
            log.warning("unexpected tz-aware timestring, overwrite as UTC: %s", s)

        # Attach UTC timezone.
        return dt.replace(tzinfo=timezone.utc)

    # Handle case where input is a single string.
    if isinstance(input, str):
        return _convert(input)

    # Handle case where input is a list of strings.
    return [_convert(s) for s in input]


def dedent_rejoin(s: str):
    """
    Remove common leading whitespace, replace newlines by spaces.

    Useful for being able to write marshmallow property docstrings with
    indented block paragraphs.
    """
    return " ".join(textwrap.dedent(s).strip().splitlines())


def dt_shift_to_utc(dt: Union[datetime, None]) -> Union[datetime, None]:
    """
    If the provided datetime object has a non-UTC `tzinfo` set then transform
    the time to UTC.

    This is expected to be called by the application only for tz-aware datetime
    objects, but it does not crash for tz-naive objects.

    tz-naive objects are returned unmodified.
    """
    if dt is not None and dt.tzinfo and dt.tzinfo != timezone.utc:
        # Change timezone to UTC, and also chang the numerical values so that
        # the same point in time is retained (change coordinate system).
        dt = dt.astimezone(timezone.utc)

    return dt


class Connection:
    def __init__(self):
        self.config = Config(get_config())
        self.session = None

    def publish(self, benchmark):
        self.post(self.config.benchmarks_url, benchmark)

    def post(self, url, data):
        if self.session:
            # already authenticated, just do post
            self._post(url, data, 201)

        if not self.session:
            # not already authenticated, or authentication expired (try again)
            self._post(self.config.login_url, self.config.credentials, 204)
            self._post(url, data, 201)

    def _post(self, url, data, expected):
        try:
            if not self.session:
                self.session = requests.Session()
                self.session.mount("https://", adapter)
            start = time.monotonic()
            response = self.session.post(url, json=data)
            log.info("Time to POST %s: %.5f s", url, time.monotonic() - start)
            if response.status_code != expected:
                self._unexpected_response("POST", response, url)
        except requests.exceptions.ConnectionError:
            self.session = None

    def _unexpected_response(self, method, response, url):
        self._print_error(f"\n{method} {url} failed", red=True)
        if response.content:
            try:
                message = json.loads(response.content)
                self._print_error(f"{json.dumps(message, indent=2)}\n")
            except json.JSONDecodeError:
                self._print_error(f"{response.content}\n")
        self.session = None

    def _print_error(self, msg, red=False):
        if red:
            click.echo(click.style(msg, fg="red"))
        else:
            click.echo(msg)


def places_to_look():
    current_dir = os.getcwd()
    benchmarks_dir = os.path.join(current_dir, "benchmarks")
    if os.path.exists(benchmarks_dir):
        return [current_dir, benchmarks_dir]
    return [current_dir]


class Config:
    def __init__(self, config):
        url = config.get("url", "http://localhost:5000")
        email = config.get("email", "conbench@example.com")
        password = str(config.get("password", "conbench"))
        self.host_name = config.get("host_name")
        self.login_url = urllib.parse.urljoin(url, "api/login/")
        self.benchmarks_url = urllib.parse.urljoin(url, "api/benchmarks/")
        self.credentials = {"email": email, "password": password}


def get_config(filename=None):
    """Get config from a yaml file named .conbench in the current
    working directory, or a sub directory called "benchmarks".
    """
    config = {}
    if filename is None:
        filename = ".conbench"
    for directory in places_to_look():
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            with open(file_path) as f:
                return yaml.load(f, Loader=yaml.FullLoader)
    return config


def register_benchmarks(directory=None):
    """Look for files matching the following patterns in the current
    working directory or a sub directory called "benchmarks", and
    import them.

        benchmark*.py
        *benchmark.py
        *benchmarks.py

    This registers benchmarks that are decorated as conbench benchmarks.

        import conbench.runner

        @conbench.runner.register_benchmark
        class ExampleBenchmark:
            ...

    It also registers the benchmark list class.

        import conbench.runner

        @conbench.runner.register_list
        class ExampleBenchmarkList:
            ...
    """
    dirs = places_to_look() if directory is None else [directory]
    for directory in dirs:
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
                    filename.startswith("benchmark")
                    or filename.endswith("benchmark.py")
                    or filename.endswith("benchmarks.py")
                ):
                    import_path(f"{directory}/{filename}", root=entry)
