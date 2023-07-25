import datetime
import functools
from io import BytesIO
from typing import List

import orjson
import pandas as pd
from flask import send_file

import conbench.numstr
from conbench.buildinfo import BUILD_INFO
from conbench.config import Config

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ..entities._entity import NotFound
from ..entities.history import HistorySample, get_history_for_benchmark
from ._resp import json_response_for_byte_sequence  # , csv_response_for_byte_sequence


class HistoryEntityAPI(ApiEndpoint):
    @maybe_login_required
    def get(self, benchmark_result_id):
        """
        ---
        description: Get benchmark history.
        responses:
            "200": "HistoryList"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        tags:
          - History
        """
        # TODO: think about the case where samples if of zero length. Can this
        # happen? If it can happen: which response would we want to emit to the
        # HTTP client? An empty array, or something more convenient?
        try:
            samples = get_history_for_benchmark(benchmark_result_id=benchmark_result_id)
        except NotFound:
            self.abort_404_not_found()

        # Note: wrap this into an array if there is just 1 sample, for
        # consistency (clients expect an array).
        jsonbytes: bytes = orjson.dumps(
            [s._dict_for_api_json() for s in samples],
            option=orjson.OPT_INDENT_2,
        )
        return json_response_for_byte_sequence(jsonbytes, 200)


class HistoryDownloadAPI(ApiEndpoint):
    @maybe_login_required
    def get(self, benchmark_result_id):
        """
        ---
        description: Download time series
        responses:
            "200": "HistoryList"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        tags:
          - History
        """
        # TODO: think about the case where samples if of zero length. Can this
        # happen? If it can happen: which response would we want to emit to the
        # HTTP client? An empty array, or something more convenient?
        try:
            items = get_history_for_benchmark(benchmark_result_id=benchmark_result_id)
        except NotFound:
            self.abort_404_not_found()

        csv_buf = generate_csv_history_for_result(benchmark_result_id, items)

        return send_file(
            csv_buf,
            as_attachment=True,
            # Use a "timeseries" fingerprint here that represents what all data
            # points in this series have in common: benchmark name, case perm,
            # hardware, context, repo.
            download_name=f"conbench-history-{items[0].benchmark_name}-{items[0].ts_fingerprint}.csv",
            mimetype="text/csv",
        )

        # # Note: wrap this into an array if there is just 1 sample, for
        # # consistency (clients expect an array).
        # jsonbytes: bytes = orjson.dumps(
        #     [s._dict_for_api_json() for s in samples],
        #     option=orjson.OPT_INDENT_2,
        # )
        # return csv_response_for_byte_sequence(csv_buf.getbuffer(), 200)


history_entity_view = HistoryEntityAPI.as_view("history")
history_download_endpoint = HistoryDownloadAPI.as_view("history-download")

rule(
    "/history/download/<benchmark_result_id>/",
    view_func=history_download_endpoint,
    methods=["GET"],
)


rule(
    "/history/<benchmark_result_id>/",
    view_func=history_entity_view,
    methods=["GET"],
)

# deduplicate: move to conbench.numstr
numstr8 = functools.partial(conbench.numstr.numstr, sigfigs=8)


def generate_csv_history_for_result(
    input_result_id: str, items: List[HistorySample]
) -> BytesIO:
    """
    input from `get_history_for_benchmark()`. Intrinsics of that function
    matter a lot; read its docstring and code. For example, two important
    aspects about that func:
    - results for default branch only
    - order is not guaranteed in returned collection.
    """

    assert len(items) > 0

    # Note that this might start to have similarities to the dataframe aspects
    # within entities.history.execute_history_query_get_dataframe() -- that's
    # expected. let's streamline internal and external interface in the future
    # and then we can make analysis on these dataframes (easy-ish) testable.
    df = pd.DataFrame(
        # Note(jp:): cannot use a generator expression here, len needs
        # to be known.
        {
            "result_id": [i.benchmark_result_id for i in items],
            "commit_hash": [i.commit_hash for i in items],
            "svs": [i.svs for i in items],
            "min": [min(i.data) for i in items],
        },
        # Note(jp): also no generator expression possible. The
        # `unit="s"` is the critical ingredient to convert this list of
        # floaty unix timestamps to datetime representation. `utc=True`
        # is required to localize the pandas DateTimeIndex to UTC
        # (input is tz-naive).
        index=pd.to_datetime([i.commit_timestamp for i in items], utc=True),
    )

    # Sort by time. old -> new
    df = df.sort_index()
    df.index.rename("commit_time", inplace=True)

    now_iso = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )

    buf = BytesIO()

    # buf.write(f"# generated by conbench {BUILD_INFO.commit}\n".encode("utf-8"))
    # buf.write(f)

    # We should expose all relevant meta data about this time series.
    # benchmark name, case permutation, hardware, repository, ..
    # Maybe it makes sense to emit HDF5 or parquet or any other file format
    # that is better at storing meta data. But here we just get going now.
    header = "\n".join(
        [
            f"# original URL: {Config.INTENDED_BASE_URL}api/history/download/{input_result_id}",
            f"# generated by conbench, commit {BUILD_INFO.commit}",
            f"# generated at {now_iso}",
            f"# for result {input_result_id}",
            f"# benchmark name: {items[0].benchmark_name}",
            f"# case permutation: {items[0].case_text_id}",
            f"# hardware hash: {items[0].hardware_hash}",
            f"# timeseries fingerprint: {items[0].ts_fingerprint}",
            f"# single value summary (SVS) type: {items[0].svs_type}",
        ]
    )

    buf.write(header.encode("utf-8"))
    buf.write(b"\n")

    df.to_csv(buf, na_rep="NaN", float_format=numstr8, encoding="utf-8")

    # Make it so that this can be treated as file object, with read() from start.
    buf.seek(0)

    return buf
