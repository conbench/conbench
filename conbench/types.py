# Do this for case ID, etc, too.

from typing import NewType, Tuple

TBenchmarkName = NewType("TBenchmarkName", str)


# This type is used often. It's the famous 4-tuple defining a time series:
# benchmark name, hardware ID, context ID, case ID. Maybe turn this into a
# namedtuple or sth like this. Watch out a bit for mem consumption.
Tt4 = Tuple[TBenchmarkName, str, str, str]
