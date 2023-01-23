from datetime import timezone

from conbench.util import tznaive_iso8601_to_tzaware_dt


def test_tznaive_iso8601_to_tzaware_dt():
    # Confirm that UTC tzinfo is attached.
    dt = tznaive_iso8601_to_tzaware_dt("2022-03-03T19:48:06")
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2022
    assert dt.second == 6
    assert dt.hour == 19

    # Confirm that UTC tzinfo in input is OK.
    dt = tznaive_iso8601_to_tzaware_dt("2022-03-03T19:48:06Z")
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2022
    assert dt.second == 6
    assert dt.hour == 19

    # Confirm that any non-UTC tzinfo in the input gets replaced with
    # UTC, retaining the numbers.
    dt = tznaive_iso8601_to_tzaware_dt("2022-03-03T19:48:06+02:00")
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2022
    assert dt.second == 6
    assert dt.hour == 19
