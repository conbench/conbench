"""Smoke test for the generated Conbench Python client (codegen pipeline proof).

It imports the client generated from api/openapi.yaml and asserts the expected
operations and models exist, proving the spec produces a usable client. With
CONBENCH_SERVER_URL set it also calls selected endpoints against a running
server; otherwise those live checks are skipped (the full live path is the
keystone e2e's job, a separate leaf).
"""

import os

import pytest


def test_generated_client_exposes_operations_and_models() -> None:
    from conbench import AuthenticatedClient, Client
    from conbench.api.default import (
        compare_benchmark_results,
        get_ci_report,
        get_benchmark_result,
        get_history,
        get_history_for_result,
        list_series,
        ping,
        submit_result,
    )
    from conbench.migration import submit_results, write_result_payloads
    from conbench.models import (
        CompareAnalysis,
        CompareResult,
        CompareSide,
        CIReport,
        CIReportComparisonStatus,
        CIReportRun,
        CIReportSummary,
        HistorySample,
        HistorySeries,
        SeriesListItem,
        SeriesPage,
        SubmitRequest,
    )

    for op in (
        list_series,
        compare_benchmark_results,
        get_ci_report,
        get_benchmark_result,
        get_history,
        get_history_for_result,
        submit_result,
        ping,
    ):
        assert hasattr(op, "sync_detailed"), op.__name__

    assert hasattr(SubmitRequest, "to_dict")
    assert hasattr(HistorySeries, "from_dict")
    assert HistorySample is not None
    assert hasattr(SeriesPage, "from_dict")
    assert hasattr(SeriesListItem, "to_dict")
    assert hasattr(CompareResult, "from_dict")
    assert hasattr(CompareSide, "to_dict")
    assert CompareAnalysis is not None
    assert hasattr(CIReport, "from_dict")
    assert CIReportComparisonStatus.REGRESSED.value == "regressed"
    assert CIReportComparisonStatus.MISSING_BASELINE.value == "missing_baseline"
    assert hasattr(CIReportRun, "to_dict")
    assert CIReportSummary is not None
    assert callable(submit_results)
    assert callable(write_result_payloads)
    assert Client is not None
    assert AuthenticatedClient is not None


@pytest.mark.skipif(
    not (
        os.environ.get("CONBENCH_SERVER_URL")
        and os.environ.get("CONBENCH_HISTORY_FINGERPRINT")
    ),
    reason=(
        "set CONBENCH_SERVER_URL and CONBENCH_HISTORY_FINGERPRINT to run the "
        "live history smoke check"
    ),
)
def test_get_history_live() -> None:
    from conbench import Client
    from conbench.api.default import get_history

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    fingerprint = os.environ["CONBENCH_HISTORY_FINGERPRINT"]

    resp = get_history.sync_detailed(client=client, fingerprint=fingerprint)
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    assert resp.parsed.history_fingerprint == fingerprint
    assert resp.parsed.samples is not None
    assert len(resp.parsed.samples) > 0


@pytest.mark.skipif(
    not os.environ.get("CONBENCH_SERVER_URL"),
    reason="set CONBENCH_SERVER_URL to run the live smoke check",
)
def test_list_series_live() -> None:
    from conbench import Client
    from conbench.api.default import list_series

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    resp = list_series.sync_detailed(client=client, page_size=5)
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    assert resp.parsed.series is not None


@pytest.mark.skipif(
    not (os.environ.get("CONBENCH_SERVER_URL") and os.environ.get("CONBENCH_RESULT_ID")),
    reason="set CONBENCH_SERVER_URL and CONBENCH_RESULT_ID to run the live result smoke check",
)
def test_get_benchmark_result_live() -> None:
    from conbench import Client
    from conbench.api.default import get_benchmark_result

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    result_id = os.environ["CONBENCH_RESULT_ID"]
    resp = get_benchmark_result.sync_detailed(client=client, id=result_id)
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    assert resp.parsed.id == result_id
    if os.environ.get("CONBENCH_HISTORY_FINGERPRINT"):
        assert resp.parsed.history_fingerprint == os.environ["CONBENCH_HISTORY_FINGERPRINT"]


@pytest.mark.skipif(
    not (
        os.environ.get("CONBENCH_SERVER_URL")
        and os.environ.get("CONBENCH_RESULT_ID")
        and os.environ.get("CONBENCH_HISTORY_FINGERPRINT")
    ),
    reason=(
        "set CONBENCH_SERVER_URL, CONBENCH_RESULT_ID, and "
        "CONBENCH_HISTORY_FINGERPRINT to run the live result-history smoke check"
    ),
)
def test_get_history_for_result_live() -> None:
    from conbench import Client
    from conbench.api.default import get_history_for_result

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    resp = get_history_for_result.sync_detailed(
        client=client,
        benchmark_result_id=os.environ["CONBENCH_RESULT_ID"],
    )
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    assert resp.parsed.history_fingerprint == os.environ["CONBENCH_HISTORY_FINGERPRINT"]
    assert resp.parsed.samples is not None
    assert len(resp.parsed.samples) > 0


@pytest.mark.skipif(
    not (
        os.environ.get("CONBENCH_SERVER_URL")
        and os.environ.get("CONBENCH_BASELINE_RESULT_ID")
        and os.environ.get("CONBENCH_CONTENDER_RESULT_ID")
    ),
    reason=(
        "set CONBENCH_SERVER_URL, CONBENCH_BASELINE_RESULT_ID, and "
        "CONBENCH_CONTENDER_RESULT_ID to run the live smoke check"
    ),
)
def test_compare_live() -> None:
    from conbench import Client
    from conbench.api.default import compare_benchmark_results

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    resp = compare_benchmark_results.sync_detailed(
        client=client,
        baseline_result_id=os.environ["CONBENCH_BASELINE_RESULT_ID"],
        contender_result_id=os.environ["CONBENCH_CONTENDER_RESULT_ID"],
    )
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    assert (
        resp.parsed.baseline.benchmark_result_id
        == os.environ["CONBENCH_BASELINE_RESULT_ID"]
    )
    assert (
        resp.parsed.contender.benchmark_result_id
        == os.environ["CONBENCH_CONTENDER_RESULT_ID"]
    )


@pytest.mark.skipif(
    not (
        os.environ.get("CONBENCH_SERVER_URL")
        and os.environ.get("CONBENCH_CI_REPORT_REPOSITORY")
        and os.environ.get("CONBENCH_CI_REPORT_COMMIT_SHA")
    ),
    reason=(
        "set CONBENCH_SERVER_URL, CONBENCH_CI_REPORT_REPOSITORY, and "
        "CONBENCH_CI_REPORT_COMMIT_SHA to run the live CI report smoke check"
    ),
)
def test_ci_report_live() -> None:
    from conbench import Client
    from conbench.api.default import get_ci_report

    client = Client(base_url=os.environ["CONBENCH_SERVER_URL"])
    kwargs = {}
    if os.environ.get("CONBENCH_CI_REPORT_THRESHOLD_Z"):
        kwargs["threshold_z"] = float(os.environ["CONBENCH_CI_REPORT_THRESHOLD_Z"])
    resp = get_ci_report.sync_detailed(
        client=client,
        repository=os.environ["CONBENCH_CI_REPORT_REPOSITORY"],
        commit_sha=os.environ["CONBENCH_CI_REPORT_COMMIT_SHA"],
        run_ids=os.environ.get("CONBENCH_CI_REPORT_RUN_IDS", ""),
        **kwargs,
    )
    assert resp.status_code == 200, resp.content
    assert resp.parsed is not None
    report = resp.parsed
    assert report.repository == os.environ["CONBENCH_CI_REPORT_REPOSITORY"]
    expected_status = os.environ.get("CONBENCH_CI_REPORT_EXPECT_STATUS")
    if expected_status:
        assert getattr(report.status, "value", report.status) == expected_status
    expected_baseline = os.environ.get("CONBENCH_CI_REPORT_EXPECT_BASELINE_RUN_ID")
    if expected_baseline:
        assert report.runs is not None
        assert len(report.runs) == 1
        assert report.runs[0].baseline_run_id == expected_baseline
    expected_contender_results = os.environ.get(
        "CONBENCH_CI_REPORT_EXPECT_CONTENDER_RESULTS"
    )
    if expected_contender_results:
        assert report.summary.contender_results == int(expected_contender_results)
    expected_regressions = os.environ.get("CONBENCH_CI_REPORT_EXPECT_REGRESSIONS")
    if expected_regressions:
        assert report.summary.regressions == int(expected_regressions)
