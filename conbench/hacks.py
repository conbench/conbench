import logging
from typing import Dict, List

from conbench.entities.benchmark_result import BenchmarkResult

log = logging.getLogger(__name__)


def _get_case_kvpair_strings(tags: Dict[str, str]) -> List[str]:
    """
    Build and and return a sorted list of strings, each item reflecting a
    (label/tag) key/value pair, all of which together define the "case
    permutation" of this conceptual benchmark.

    The returned list might be of length 0 when `tags` has only one key called
    "name".

    Each item takes the shape key=value.

    Special keys are omitted (does that make sense?)

    Keep those with None value.

    TODO: move to different module
    """
    return [f"{k}={v}" for k, v in sorted(tags.items()) if k not in ("name")]


def set_display_case_permutation(bmresult: Dict | BenchmarkResult):
    """
    Build and set a string reflecting the case permutation (specific variation
    of str/str key/value pairs, each pair reflecting a case parameter) for this
    benchmark result object.

    TODO: move to different module
    """

    # Extract `tags` object.
    if isinstance(bmresult, BenchmarkResult):
        tags: Dict[str, str] = bmresult.case.tags
    else:
        tags = bmresult["tags"]

    # Note(JP): On the input side of things, we pulled the `name=<bmname>` pair
    # out of tags, and stored it on case.name (and stored remaining case.tags
    # separately). These next lines re-add the benchmark name into `tags`, to
    # keep output and input symmetric, I suppose. However, in the future, we
    # should emphasize better thant it is the combination of name+case_perm
    # which must be unique, and it is OK to store both separately, and
    # represent both separately in the output. I am in favor returning,
    # conceptually, something like this:
    #
    #    {"benchmark_name": name, "benchmark_case": casetags}
    #
    # I think this is clearer than returning {"tags": tags} where `tags` then
    # contains everything.
    #
    # If is_api is True then this is a dictionary and the name key is already
    # in tags! See benchmark_result.py serializer... woof.
    if isinstance(bmresult, BenchmarkResult):
        benchmark_name = bmresult.case.name
        tags["name"] = benchmark_name
    else:
        # This is the result of a needless re-serialization cycle
        # Test if we can work with that assumption
        if "name" not in tags:
            log.warning("dict bm result w/o name in tags")

    caseperm_string_chunks = _get_case_kvpair_strings(tags)

    result = ", ".join(caseperm_string_chunks)
    if len(caseperm_string_chunks) == 0:
        result = "no-permutations"

    if isinstance(bmresult, BenchmarkResult):
        bmresult.display_case_perm = result
    else:
        bmresult["display_case_perm"] = result


def set_display_benchmark_name(bmresult):
    """
    Build and set a string reflecting the benchmark identity (the conceptual
    benchmark) for this benchmark result.

    TODO: move to different module
    """
    is_api = isinstance(bmresult, dict)
    # will this next line not raise a KeyError of is_api is false?
    tags = bmresult["tags"] if is_api else bmresult.case.tags
    name = tags.get("name") if is_api else bmresult.case.name

    if is_api:
        bmresult["display_bmname"] = name
    else:
        bmresult.display_bmname = name


def sorted_data(benchmarks):
    """
    TODO: identify what this does, assess the value, and re-implement in
    a different module.
    """
    data = []
    for benchmark in benchmarks:
        if benchmark["error"]:
            continue

        tags = benchmark["tags"]
        case = _get_case_kvpair_strings(tags)
        case.append(benchmark["stats"]["mean"])
        data.append(case)

    # Try to sort the cases better
    # unsorted: ['262144/0', '262144/1', '262144/10', '262144/2']
    # sorted: [[262144, 0], [262144, 1], [262144, 2], [262144, 10]]
    new_data = []
    for row in data:
        case = row[0]
        parts = []
        for x in case.split("/"):
            try:
                parts.append(int(x))
            except:
                parts.append(x)
        new_data.append([parts, row])
    new_data = sorted(new_data)

    return [row[1] for row in new_data]


# Note(JP): Keeping this here because this turned out to be highly useful and
# we want to maybe re-use that. I started with
# https://goshippo.com/blog/measure-real-size-any-python-object/ and
# https://stackoverflow.com/a/40880923 and then brute-forced may way through
# Flask/SQLAlchemy special conditions. This tries to answer "How big is this
# object" in memory? I applied it to a big dictionary which held other
# dictionaries which held SQLAlchemy DB entity-entangled objects
# (DeclarativeBase-derived) entangled with Flask/werkzeug-app context /
# "request locals". My goal was to get this to count at least something. The
# special cases below with dubious handling happen rarely, i.e. this counts the
# majority of what matters. Note however for result interpretation you need to
# understand some things about CPython's memory management (string interning,
# etc). The more macroscopic view (heap size of CPython process is after all
# showing if changes/insights are helpful or not). I am ke def get_size(obj,
# seen=None): """Recursively finds size of objects"""

#     if obj is None:
#         return 0

#     if isinstance(obj, werkzeug.local.ContextVar):
#         return 0

#     size = sys.getsizeof(obj)

#     if seen is None:
#         seen = set()

#     obj_id = id(obj)
#     if obj_id in seen:
#         return 0
#     # Important mark as seen *before* entering recursion to gracefully handle
#     # self-referential objects
#     seen.add(obj_id)

#     if isinstance(obj, dict):
#         size += sum([get_size(v, seen) for v in obj.values()])
#         size += sum([get_size(k, seen) for k in obj.keys()])

#     elif hasattr(obj, "__dict__"):
#         try:
#             size += get_size(obj.__dict__, seen)
#         except RuntimeError:
#             # handle werkzeug.local special context var protection:
#             # https://github.com/pallets/werkzeug/blob/2.2.3/src/werkzeug/local.py
#             log.info("ignore werkzeug RuntimeErr")
#             return 0

#     elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):
#         if obj is None:
#             return 0

#         # from typing import _SpecialForm.
#         if isinstance(obj, _SpecialForm):
#             # Ignore this obj: TypeError: '_SpecialForm' object is not iterable
#             return 0

#         try:
#             size += sum([get_size(i, seen) for i in obj])
#         except TypeError:
#             # Might still fail with
#             # TypeError: 'NoneType' object is not iterable
#             log.info("ignore not-yet-understood TypeError")
#             seen.add(id(obj))
#             return 0
#     return size
