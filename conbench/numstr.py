"""
A module for turning a floating point number into short, meaningful text, for
representation in a user interface, or in e.g. JSON documents.

Guidelines:

- no unnecessary precision (reasonable number of significant digits)
- shortest possible output (e.g., no trailing ".0" or even ".")

At first we started using sigfig.round() but then we noticed that it's
incredibly unnecessarily slow. See
https://github.com/conbench/conbench/issues/1218

Then I found a test case that fails for sigfig.round(), but does not for

    sigfig.round(15272063, 5) produces "15272000.0", i.e. here we have the
    unnecessary .0 suffix.

Then I researched further options and gladly found np.format_float_positional()
from numpy. It uses the so-called Dragon4 algorithm with all its beautiful
configuration options for stringifying floats. Found a set of configuration
options that achieves the desired results across test cases. Rough timing
experiments show that this function is about three orders of magnitude faster
than sigfig.round(), that's a nice performance win side effect here from trying
to get a more 'correct' result! Beautiful.

Note: for particularly small or large numbers we can start using
npformat_float_scientific().

Timing results on my machine (stdout of this program when invoked as main
module):

sigfig : sigfig.round(0.000123888129341456, sigfigs=5)  -->  0.337580 s
numstr : numstr(0.000123888129341456, 5)  -->  0.002462 s
---
sigfig : sigfig.round(015272063.0, sigfigs=3)  -->  0.244474 s
numstr : numstr(015272063.0, 3)  -->  0.002069 s
---
sigfig : sigfig.round(9.738480924743*10**8, sigfigs=7)  -->  0.317508 s
numstr : numstr(9.738480924743*10**8, 7)  -->  0.002376 s
---
sigfig : sigfig.round(982378347837483, sigfigs=7)  -->  0.318014 s
numstr : numstr(982378347837483, 7)  -->  0.002471 s

"""

import timeit
from typing import Union

import numpy as np

# import sigfig


def numstr(v: Union[float, int], sigfigs: int = 5) -> str:
    """
    Turn number into string while limiting the number of significant figures.

    Examples:

    >>> numstr(0.00123912382981923, 5)
    '0.0012391'

    >>> numstr(1232132923.2378, 5)
    '1232100000'
    """
    # Trim trailing zeros and any trailing decimal point. `fractional=False`
    # means that the `precision` arg refers to the total number of significant
    # digits, before or after the decimal point, ignoring leading zeros.
    return np.format_float_positional(v, precision=sigfigs, trim="-", fractional=False)


_conversion_correctness_tests = (
    (15272063, "15272000"),  #
    # Works with float and int input.
    # Does not add trailing . or even .0
    (15272063.0, "15272000"),
    (015272063.0, "15272000"),  # Works with leading zero in input
    (1.2345, "1.2345"),  # Keeps things unmodified
    (1.23456, "1.2346"),  # Performs rounding
    (0.00123898129341456, "0.001239"),  # Cut to N-1 if last digit is 9
    (0.00123888129341456, "0.0012389"),  # part of above's test
    # Works for small numbers.
    (
        0.0000000000000000054755754547541,
        "0.0000000000000000054756",
    ),
    # Works for big numbers.
    (
        9237842376728342980347982,
        "9237800000000000000000000",
    ),
)

if __name__ == "__main__":
    # Run tests.
    for nbr, expected in _conversion_correctness_tests:
        # got = numstr(nbr)
        # got = str(sigfig.round(nbr, sigfigs=5))
        got = str(sigfig.round(nbr, sigfigs=5))
        assert (
            got == expected
        ), f"input: {repr(nbr)} -- expected {expected} but got {got}"

    # Do a bit of a performance comparison:
    for value, figs in (
        ("0.000123888129341456", 5),
        ("015272063.0", 3),
        ("9.738480924743*10**8", 7),
        ("982378347837483", 7),
    ):
        for name, funcstring in (
            ("sigfig", f"sigfig.round({value}, sigfigs={figs})"),
            ("numstr", f"numstr({value}, {figs})"),
        ):
            result = timeit.timeit(funcstring, number=5000, globals=globals())
            print(name, ":", funcstring, " --> ", f"{result:6f} s")

        print("---")
