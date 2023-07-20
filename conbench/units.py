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

KNOWN_UNITS = {
    "B/s": {
        "long": "bytes per second",
        "less_is_better": False,
    },
    "s": {
        "long": "seconds",
        "less_is_better": True,
    },
    "ns": {
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


KNOWN_UNIT_SYMBOLS = list(KNOWN_UNITS.keys())
KNOWN_UNIT_SYMBOLS_STR = ", ".join(KNOWN_UNIT_SYMBOLS)
