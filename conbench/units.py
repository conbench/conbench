from typing import Optional

import sigfig


def items_per_second_fmt(value, unit):
    # Note this func probably suffers from truncating small values:
    # https://github.com/conbench/conbench/issues/683
    if value is None:
        return None
    if value < 1000:
        return "{} {}".format(value, unit)
    if value < 1000**2:
        return "{:.3f} K {}".format(value / 1000, unit)
    if value < 1000**3:
        return "{:.3f} M {}".format(value / 1000**2, unit)
    else:
        return "{:.3f} G {}".format(value / 1000**3, unit)


def bytes_per_second_fmt(value, unit):
    # Note this func probably suffers from truncating small values:
    # https://github.com/conbench/conbench/issues/683
    if value is None:
        return None
    if value < 1024:
        return "{} {}".format(value, unit)
    if value < 1024**2:
        return "{:.3f} Ki{}".format(value / 1024, unit)
    if value < 1024**3:
        return "{:.3f} Mi{}".format(value / 1024**2, unit)
    if value < 1024**4:
        return "{:.3f} Gi{}".format(value / 1024**3, unit)
    else:
        return "{:.3f} Ti{}".format(value / 1024**4, unit)


def fmt_unit(value: Optional[float], unit) -> Optional[str]:
    # Maybe simplify function signature and never allow this to be called
    # with None.
    if value is None:
        return None

    # These stringified values power a Bokeh plot. Ensure that the textual
    # representation of the numeric value encodes a desired minimum number of
    # significant digits, to allow for meaningful plotting resolution.
    # With a fixed "floating point number precision", rather small values
    # appear trucated: https://github.com/conbench/conbench/issues/683

    # I have seen a KeyError being thrown which I could not reproduce anymore.
    # sigfig/sigfig.py line 551 does `del number.map[p]` and this resulted in
    # `KeyError: 0`. It was probably a programming mistake.
    return f"{sigfig.round(value, sigfigs=4)} {unit}"


def formatter_for_unit(unit):
    if unit == "B/s":
        return bytes_per_second_fmt
    elif unit == "i/s":
        return items_per_second_fmt
    else:
        return fmt_unit
