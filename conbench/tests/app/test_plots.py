import datetime

from ...app._plots import _should_format, _simple_source, _source

HISTORY = [
    {
        "benchmark_id": "b4466622481f4e3a927e962008309724",
        "case_id": "bdca99e75fee41e8aec77c2c1bc220ab",
        "context_id": "a348db873c3641a9a13b57e934984525",
        "distribution_mean": "392130886.117931",
        "distribution_stdev": "0.000000",
        "machine_hash": "ursa-thinkcentre-m75q-6-6-16106127360",
        "mean": "392130886.117931",
        "message": "ARROW-13429: [C++][Gandiva] Fix Gandiva codegen for if-else expression with binary type",
        "repository": "https://github.com/apache/arrow",
        "run_name": "commit: 7ee8edb68ce6ce25944ff69f333027fdeaaf93e7",
        "sha": "7ee8edb68ce6ce25944ff69f333027fdeaaf93e7",
        "timestamp": "2021-08-04T10:26:07",
        "unit": "B/s",
    },
    {
        "benchmark_id": "de97178de12846c7bd9252f998150bff",
        "case_id": "bdca99e75fee41e8aec77c2c1bc220ab",
        "context_id": "a348db873c3641a9a13b57e934984525",
        "distribution_mean": "388236410.822258",
        "distribution_stdev": "5507619.781468",
        "machine_hash": "ursa-thinkcentre-m75q-6-6-16106127360",
        "mean": "384341935.526585",
        "message": "ARROW-12388: [C++][Gandiva] Implement cast numbers from varbinary functions in gandiva",
        "repository": "https://github.com/apache/arrow",
        "run_name": "commit: c4e53e09fe6964f404fe0fa89a5d3eb8a2607442",
        "sha": "c4e53e09fe6964f404fe0fa89a5d3eb8a2607442",
        "timestamp": "2021-08-04T10:28:54",
        "unit": "B/s",
    },
    {
        "benchmark_id": "27f3b6fda2d64fe4b4cc2af16ccefc00",
        "case_id": "bdca99e75fee41e8aec77c2c1bc220ab",
        "context_id": "a348db873c3641a9a13b57e934984525",
        "distribution_mean": "386395506.239738",
        "distribution_stdev": "5033262.051040",
        "machine_hash": "ursa-thinkcentre-m75q-6-6-16106127360",
        "mean": "382713697.074697",
        "message": "ARROW-12479: [C++][Gandiva] Implement castBigInt, castInt, castIntervalDay and castIntervalYear extra functions",
        "repository": "https://github.com/apache/arrow",
        "run_name": "commit: 87e0252abc14cd6925857d613b8865a1eebf9ba3",
        "sha": "87e0252abc14cd6925857d613b8865a1eebf9ba3",
        "timestamp": "2021-08-04T10:30:10",
        "unit": "B/s",
    },
    {
        "benchmark_id": "feac4ec1ca014a6bb7b7cb84869cdebb",
        "case_id": "bdca99e75fee41e8aec77c2c1bc220ab",
        "context_id": "a348db873c3641a9a13b57e934984525",
        "distribution_mean": "387124231.233692",
        "distribution_stdev": "4360425.634830",
        "machine_hash": "ursa-thinkcentre-m75q-6-6-16106127360",
        "mean": "389310406.215554",
        "message": "ARROW-12410: [C++][Gandiva] Implement regexp_replace function on Gandiva",
        "repository": "https://github.com/apache/arrow",
        "run_name": "commit: 5f0641b29f170ee4faac058f6d26d72d7747bcc3",
        "sha": "5f0641b29f170ee4faac058f6d26d72d7747bcc3",
        "timestamp": "2021-08-04T10:31:35",
        "unit": "B/s",
    },
    {
        "benchmark_id": "eca009ba5ce0427ab32fadeb28d27143",
        "case_id": "bdca99e75fee41e8aec77c2c1bc220ab",
        "context_id": "a348db873c3641a9a13b57e934984525",
        "distribution_mean": "387968509.336751",
        "distribution_stdev": "4221849.282505",
        "machine_hash": "ursa-thinkcentre-m75q-6-6-16106127360",
        "mean": "391345621.748988",
        "message": "ARROW-12866: [C++][Gandiva] Implement STRPOS function on Gandiva",
        "repository": "https://github.com/apache/arrow",
        "run_name": "commit: bc175f9f4e6575bfbaaabe84aecde13244330c1e",
        "sha": "bc175f9f4e6575bfbaaabe84aecde13244330c1e",
        "timestamp": "2021-08-04T10:36:39",
        "unit": "B/s",
    },
]

DATES = [
    datetime.datetime(2021, 8, 4, 10, 26, 7),
    datetime.datetime(2021, 8, 4, 10, 28, 54),
    datetime.datetime(2021, 8, 4, 10, 30, 10),
    datetime.datetime(2021, 8, 4, 10, 31, 35),
    datetime.datetime(2021, 8, 4, 10, 36, 39),
]
COMMITS = [
    "ARROW-13429: [C++][Gandiva] Fix Gandiva codegen for if-else expression with binary type",
    "ARROW-12388: [C++][Gandiva] Implement cast numbers from varbinary functions in gandiva",
    "ARROW-12479: [C++][Gandiva] Implement castBigInt, castInt, castIntervalDay and castIntervalYear extra functions",
    "ARROW-12410: [C++][Gandiva] Implement regexp_replace function on Gandiva",
    "ARROW-12866: [C++][Gandiva] Implement STRPOS function on Gandiva",
]
POINTS = [
    "392130886.117931",
    "384341935.526585",
    "382713697.074697",
    "389310406.215554",
    "391345621.748988",
]
POINTS_FORMATTED = [
    "373.965",
    "366.537",
    "364.984",
    "371.275",
    "373.216",
]
MEANS = [
    "373.965 MiB/s",
    "366.537 MiB/s",
    "364.984 MiB/s",
    "371.275 MiB/s",
    "373.216 MiB/s",
]
POINTS_FORMATTED_ITEMS = [
    "392.131",
    "384.342",
    "382.714",
    "389.310",
    "391.346",
]
MEANS_ITEMS = [
    "392.131 M i/s",
    "384.342 M i/s",
    "382.714 M i/s",
    "389.310 M i/s",
    "391.346 M i/s",
]
POINTS_MIN = [
    392130886.117931,
    360698311.914918,
    361229195.98453796,
    365322103.059542,
    366859262.924226,
]
POINTS_MIN_FORMATTED = [
    "373.965",
    "343.989",
    "344.495",
    "348.398",
    "349.864",
]
POINTS_MAX = [
    392130886.117931,
    415774509.729598,
    411561816.494938,
    408926359.407842,
    409077755.749276,
]
POINTS_MAX_FORMATTED = [
    "373.965",
    "396.513",
    "392.496",
    "389.983",
    "390.127",
]
MEANS_MIN = [
    "373.965 MiB/s",
    "343.989 MiB/s",
    "344.495 MiB/s",
    "348.398 MiB/s",
    "349.864 MiB/s",
]
MEANS_MAX = [
    "373.965 MiB/s",
    "396.513 MiB/s",
    "392.496 MiB/s",
    "389.983 MiB/s",
    "390.127 MiB/s",
]


def test__source():
    source = _source(HISTORY, "B/s")
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS
    assert source.data["means"] == MEANS
    assert source.data["commits"] == COMMITS


def test_source_formatted():
    source = _source(HISTORY, "B/s", formatted=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_FORMATTED
    assert source.data["means"] == MEANS
    assert source.data["commits"] == COMMITS


def test_source_formatted_items_per_second():
    source = _source(HISTORY, "i/s", formatted=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_FORMATTED_ITEMS
    assert source.data["means"] == MEANS_ITEMS
    assert source.data["commits"] == COMMITS


def test_source_alert_min():
    source = _source(HISTORY, "B/s", alert_min=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_MIN
    assert source.data["means"] == MEANS_MIN
    assert source.data["commits"] == COMMITS


def test_source_alert_min_formatted():
    source = _source(HISTORY, "B/s", alert_min=True, formatted=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_MIN_FORMATTED
    assert source.data["means"] == MEANS_MIN
    assert source.data["commits"] == COMMITS


def test_source_alert_max():
    source = _source(HISTORY, "B/s", alert_max=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_MAX
    assert source.data["means"] == MEANS_MAX
    assert source.data["commits"] == COMMITS


def test_source_alert_max_formatted():
    source = _source(HISTORY, "B/s", alert_max=True, formatted=True)
    assert source.data["x"] == DATES
    assert source.data["y"] == POINTS_MAX_FORMATTED
    assert source.data["means"] == MEANS_MAX
    assert source.data["commits"] == COMMITS


def test_should_format():
    history = [
        {
            "mean": "392130886.117931",
        },
        {
            "mean": "492130886.117931",
        },
        {
            "mean": "592130886.117931",
        },
    ]
    assert _should_format(history, "s") == (True, "seconds")
    assert _should_format(history, "B/s") == (True, "MiB/s")
    assert _should_format(history, "i/s") == (True, "M i/s")
    assert _should_format(history, "other") == (True, "other")


def test_should_format_values_too_small():
    history = [
        {
            "mean": "1.117931",
        },
        {
            "mean": "2.117931",
        },
        {
            "mean": "3.117931",
        },
    ]
    assert _should_format(history, "s") == (True, "seconds")
    assert _should_format(history, "B/s") == (True, "bytes/second")
    assert _should_format(history, "i/s") == (True, "items/second")
    assert _should_format(history, "other") == (True, "other")


def test_should_format_units_not_uniform():
    history = [
        {
            "mean": "392130886.117931",
        },
        {
            "mean": "886.117931",
        },
        {
            "mean": "592130886.117931",
        },
    ]
    assert _should_format(history, "s") == (True, "seconds")
    assert _should_format(history, "B/s") == (False, "bytes/second")
    assert _should_format(history, "i/s") == (False, "items/second")
    assert _should_format(history, "other") == (True, "other")


def test_simple_source():
    data = [
        ["table", "911746389.191990"],
        ["download", "9836828.070182"],
        ["parquet", "138695784.072201"],
    ]
    source, axis_unit = _simple_source(data, "B/s")
    assert axis_unit == "MiB/s"
    assert source.data["x"] == [
        "table",
        "download",
        "parquet",
    ]
    assert source.data["y"] == [
        "869.509",
        "9.381",
        "132.271",
    ]
    assert source.data["means"] == [
        "869.509 MiB/s",
        "9.381 MiB/s",
        "132.271 MiB/s",
    ]


def test_simple_source_items_per_second():
    data = [
        ["table", "911746389.191990"],
        ["download", "9836828.070182"],
        ["parquet", "138695784.072201"],
    ]
    source, axis_unit = _simple_source(data, "i/s")
    assert axis_unit == "M i/s"
    assert source.data["x"] == [
        "table",
        "download",
        "parquet",
    ]
    assert source.data["y"] == [
        "911.746",
        "9.837",
        "138.696",
    ]
    assert source.data["means"] == [
        "911.746 M i/s",
        "9.837 M i/s",
        "138.696 M i/s",
    ]


def test_simple_source_units_not_uniform():
    data = [
        ["table", "911746389.191990"],
        ["download", "983.070182"],
        ["parquet", "138695784.072201"],
    ]
    source, axis_unit = _simple_source(data, "B/s")
    assert axis_unit == "bytes/second"
    assert source.data["x"] == [
        "table",
        "download",
        "parquet",
    ]
    assert source.data["y"] == [
        "911746389.191990",
        "983.070182",
        "138695784.072201",
    ]
    assert source.data["means"] == [
        "869.509 MiB/s",
        "983.070182 B/s",
        "132.271 MiB/s",
    ]


def test_simple_source_units_not_uniform_items_per_second():
    data = [
        ["table", "911746389.191990"],
        ["download", "983.070182"],
        ["parquet", "138695784.072201"],
    ]
    source, axis_unit = _simple_source(data, "i/s")
    assert axis_unit == "items/second"
    assert source.data["x"] == [
        "table",
        "download",
        "parquet",
    ]
    assert source.data["y"] == [
        "911746389.191990",
        "983.070182",
        "138695784.072201",
    ]
    assert source.data["means"] == [
        "911.746 M i/s",
        "983.070182 i/s",
        "138.696 M i/s",
    ]


def test_simple_source_omit_redundant_labels():
    data = [
        ["table", "tag=1", "tag 2", "100"],
        ["download", "tag=2", "tag 2", "200"],
        ["parquet", "tag=3", "tag 2", "300"],
    ]
    source, axis_unit = _simple_source(data, "s")
    assert axis_unit == "seconds"
    assert source.data["x"] == [
        "table-tag=1",
        "download-tag=2",
        "parquet-tag=3",
    ]
    assert source.data["y"] == [
        "100.000",
        "200.000",
        "300.000",
    ]
    assert source.data["means"] == [
        "100.000 s",
        "200.000 s",
        "300.000 s",
    ]
