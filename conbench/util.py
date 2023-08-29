import logging
import re
import textwrap
from datetime import datetime, timezone
from typing import List, Union, overload

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
