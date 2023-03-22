from typing import Dict, List

CASE_KEYS_DO_NOT_USE_FOR_NAME = ("id", "name", "suite", "source", "dataset")


def get_case_kvpair_strings(tags: Dict[str, str], include_dataset=False) -> List[str]:
    """
    Build and and return a list of strings, each item reflecting a key/value
    pair, all of which together define the "case permutation" of this
    conceptual benchmark.

    Each item takes the shape key=value.

    Special keys are omitted (does that make sense?)

    Keep those with None value.
    """
    kvpairs = [
        (k, v)
        for k, v in sorted(tags.items())
        if k not in CASE_KEYS_DO_NOT_USE_FOR_NAME
    ]

    # Rationale?
    if include_dataset and "dataset" in tags:
        kvpairs.append(("dataset", tags["dataset"]))

    # # Rationale?
    # if "language" in tags:
    #     kvpairs.append(("language", tags["language"]))

    # booleans = [True, False, "true", "false"]

    # case = [(k, f"{k}={v}") if v in booleans else (k, v) for k, v in case]

    # return [f"{k}={v}" if isinstance(v, (int, float)) else str(v) for k, v in case]

    return [f"{k}={v}" for k, v in kvpairs]


def set_display_case_permutation(bmresult):
    """
    Build and set a string reflecting the case permutation for this bmresult
    result.
    """
    is_api = isinstance(bmresult, dict)
    tags = bmresult["tags"] if is_api else bmresult.case.tags

    # Note(JP): this tries to pull in the benchmark name into the case
    # permutation k/v pairs. Skip this for now. Unique combination must be
    # name+case_perm, so adding the name into the case_perm again should not be
    # conceptually needed.

    # name = tags.get("name") if is_api else bmresult.case.name
    # if "name" not in tags:
    #     tags["name"] = name

    caseperm_string_chunks = get_case_kvpair_strings(tags, include_dataset=True)

    # Again, this here is related to setting the bmresult name.
    # Do not include this in the case perm string.

    # if "suite" in tags:
    #     case = [name] + case

    # name = ", ".join(case) if case else name

    result = ", ".join(caseperm_string_chunks)
    if len(caseperm_string_chunks) == 0:
        result = "no-permutations"

    if is_api:
        bmresult["display_case_perm"] = result
    else:
        bmresult.display_case_perm = result


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
