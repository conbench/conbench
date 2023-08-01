"""
Historically, Conbench allowed users to submit any unit string together with
measurement values.

This is an attempt to impose constraints. Conbench business logic can then use
properties like `less_is_better` and `long` from the lookup table below.

Note that b/s is transparently rewritten to B/s in benchmark_results.py (before
DB insertion).

Also see https://github.com/conbench/conbench/issues/1335.

About names, descriptions and hard questions about plural vs singular there
is lovely inspiration in the following resources:
https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-9-rules-and-style-conventions-spelling-unit-names
https://en.wikipedia.org/wiki/Data-rate_units
https://english.stackexchange.com/questions/22082/are-units-in-english-singular-or-plural
https://physics.stackexchange.com/questions/172039/usage-of-singular-or-plural-si-base-units-when-written-in-both-symbol-as-well-as
https://physics.stackexchange.com/questions/384187/can-units-be-plural
https://physics.nist.gov/cuu/Units/checklist.html
https://forum.thefreedictionary.com/postst144586_singular-or-plural.aspx
"""

# Map canonical symbol (established short handle) to canonical long name of a
# unit, and unit properties.
# TODO: allow for extending this via config.

from typing import Dict, Literal, TypedDict, cast

# These are the symbols. We could call this type UnitSymbol, but we can
# have the convention that whenever "unit" pops up in the code base it means
# the short version, the symbol.
TUnit = Literal["B/s", "s", "ns", "i/s"]


class TUnitDef(TypedDict):
    long: str
    less_is_better: bool


# slash ("/"") or "per"? We will see.
KNOWN_UNITS: Dict[TUnit, TUnitDef] = {
    "B/s": {
        "long": "bytes per second",
        "less_is_better": False,
    },
    "s": {
        "long": "seconds",
        "less_is_better": True,
    },
    "ns": {
        # This is here for legacy reasons, but maybe if it wasn't we would
        # have added this in addition to `s`
        "long": "nanoseconds",
        "less_is_better": True,
    },
    "i/s": {
        # iterations per second? items per second? Here, we define it as
        # iterations per second which is more general than items per second.
        "long": "iterations per second",
        "less_is_better": False,
    },
}


_KNOWN_UNIT_SYMBOLS = list(KNOWN_UNITS.keys())
KNOWN_UNIT_SYMBOLS_STR = ", ".join(_KNOWN_UNIT_SYMBOLS)
_KNOWN_UNITS_LONG: Dict[TUnit, str] = {k: v["long"] for k, v in KNOWN_UNITS.items()}
_KNOWN_UNITS_LIB: Dict[TUnit, bool] = {
    k: v["less_is_better"] for k, v in KNOWN_UNITS.items()
}


def longform(symbol: TUnit) -> str:
    return _KNOWN_UNITS_LONG[symbol]


def legacy_convert(s: str) -> TUnit:
    """
    Confirm that the passed symbol (type str) is an allowed symbol. Return it
    as type TUnit. Raise AssertionError otherwise.

    Related: https://github.com/conbench/conbench/issues/1335

    Also for now transparently rewrite `b/s` -- Legacy DB state allows for that
    for now to our knowledge.
    """
    if s == "b/s":
        return "B/s"

    assert s in KNOWN_UNITS
    return cast(TUnit, s)


def less_is_better(symbol: TUnit) -> bool:
    """
    Return less_is_better boolean for a given unit symbol (the short version,
    such as 'B/s', 's', ...). Allowed symbols are the keys in KNOWN_UNITS above.

    Related:
    https://github.com/conbench/conbench/issues/1335
    """
    return _KNOWN_UNITS_LIB[symbol]
