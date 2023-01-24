from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest

import conbench.util


@pytest.mark.parametrize(
    "teststring",
    ["2022-03-03T19:48:06", "2022-03-03T19:48:06Z", "2022-03-03T19:48:06+02:00"],
)
def test_tznaive_iso8601_to_tzaware_dt(teststring: str):
    # Confirm that
    # - UTC tzinfo is attached when input is naive.
    # - UTC tzinfo in input is OK.
    # - any non-UTC tzinfo in the input gets replaced with
    #   UTC, retaining the numbers.
    dt = conbench.util.tznaive_iso8601_to_tzaware_dt(teststring)
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2022
    assert dt.second == 6
    assert dt.hour == 19


@pytest.mark.parametrize(
    "param",
    [
        # Confirm that tz-aware dt obj does not crash function, and that
        # tz info is indeed retained, with Z technique for UTC.
        (
            datetime(2000, 10, 10, 17, 30, 55, tzinfo=timezone.utc),
            "2000-10-10T17:30:55Z",
        ),
        (
            datetime(2000, 10, 10, 17, 30, 55, tzinfo=timezone(timedelta(hours=5))),
            "2000-10-10T17:30:55+05:00",
        ),
        # Confirm taht tz-naive dt objects are interpreted in UTC.
        (datetime(2000, 10, 10, 17, 30, 55), "2000-10-10T17:30:55Z"),
        # Confirm that fractions of seconds are ignored in output.
        (datetime(2000, 10, 10, 17, 30, 55, 1337), "2000-10-10T17:30:55Z"),
    ],
)
def test_tznaive_dt_to_aware_iso8601_for_api(param: Tuple[datetime, str]):
    assert conbench.util.tznaive_dt_to_aware_iso8601_for_api(param[0]) == param[1]
