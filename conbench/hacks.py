def set_display_name(benchmark):
    is_api = isinstance(benchmark, dict)
    tags = benchmark["tags"] if is_api else benchmark.case.tags
    name = tags.get("name") if is_api else benchmark.case.name
    if "name" not in tags:
        tags["name"] = name
    case = [
        v
        for k, v in sorted(tags.items())
        if not isinstance(v, int)
        and v is not None
        and k != "id"
        and k != "source"
        and k != "name"
        and k != "suite"
    ]
    if "suite" in tags:
        case = [name] + case
    name = ", ".join(case) if case else name
    if is_api:
        benchmark["display_name"] = name
    else:
        benchmark.display_name = name


def set_display_batch(benchmark):
    is_api = isinstance(benchmark, dict)
    tags = benchmark["tags"] if is_api else benchmark.case.tags
    name = tags.get("name") if is_api else benchmark.case.name
    batch = tags.get("suite", name)
    if is_api:
        benchmark["display_batch"] = batch
    else:
        benchmark.display_batch = batch


def sorted_data(benchmarks, fields, factor=False):
    data, default_factor_bucket = [], None
    for benchmark in benchmarks:
        tags = benchmark["tags"]
        if not fields:
            items = [
                (k, v)
                for k, v in sorted(tags.items())
                if not isinstance(v, int)
                and v is not None
                and k != "id"
                and k != "name"
                and k != "dataset"
                and k != "source"
            ]
            row = [v for k, v in items]
            if factor:
                default_factor_bucket = items[-1][0]
        else:
            row = [tags[name] for name in fields]
        row.append(benchmark["stats"]["mean"])
        data.append(row)

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

    data = [row[1] for row in new_data]
    if factor:
        return data, default_factor_bucket
    return data
