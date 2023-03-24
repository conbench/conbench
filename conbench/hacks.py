import logging
from typing import Dict, List

from conbench.entities.benchmark_result import BenchmarkResult

# Note(JP): ideally this contains just a single key. I think that this here is
# purely for display purposes, not for storing in the DB. Now that I think
# about it: Let's keep things simple: this is part of the case permutation in
# the database, so show it.
#  CASE_KEYS_DO_NOT_USE_FOR_STRING = ("id", "name", "suite", "source", "dataset")


log = logging.getLogger(__name__)


def get_case_kvpair_strings(tags: Dict[str, str]) -> List[str]:
    """
    Build and and return a sorted list of strings, each item reflecting a
    (label/tag) key/value pair, all of which together define the "case
    permutation" of this conceptual benchmark.

    The returned list might be of length 0 when `tags` has only one key called
    "name".

    Each item takes the shape key=value.

    Special keys are omitted (does that make sense?)

    Keep those with None value.
    """
    return [f"{k}={v}" for k, v in sorted(tags.items()) if k not in ("name")]


def set_display_case_permutation(bmresult: Dict | BenchmarkResult):
    """
    Build and set a string reflecting the case permutation (specific variation
    of str/str key/value pairs, each pair reflecting a case parameter) for this
    benchmark result object.
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

    caseperm_string_chunks = get_case_kvpair_strings(tags)

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
    """
    is_api = isinstance(bmresult, dict)
    # will this next line not raise a KeyError of is_api is false?
    tags = bmresult["tags"] if is_api else bmresult.case.tags
    name = tags.get("name") if is_api else bmresult.case.name

    # If `suite` is a key in the tags, then use its value for `name`, ignore
    # name.
    bmname = tags.get("suite", name)
    if is_api:
        bmresult["display_bmname"] = bmname
    else:
        bmresult.display_bmname = bmname


def sorted_data(benchmarks):
    data = []
    for benchmark in benchmarks:
        if benchmark["error"]:
            continue

        tags = benchmark["tags"]
        case = get_case_kvpair_strings(tags)
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
