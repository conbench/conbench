from datetime import timezone

import pytest

from conbench.util import tznaive_iso8601_to_tzaware_dt


@pytest.mark.parametrize(
    "teststring",
    ["2022-03-03T19:48:06", "2022-03-03T19:48:06Z", "2022-03-03T19:48:06+02:00"],
)
def test_tznaive_iso8601_to_tzaware_dt(teststring: str):
    # Confirm that
    # - UTC tzinfo is attached.
    # - UTC tzinfo in input is OK.
    # - any non-UTC tzinfo in the input gets replaced with
    #   UTC, retaining the numbers.
    dt = tznaive_iso8601_to_tzaware_dt(teststring)
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2022
    assert dt.second == 6
    assert dt.hour == 19
