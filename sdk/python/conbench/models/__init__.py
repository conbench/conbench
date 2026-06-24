"""Contains all the data models used in inputs/outputs"""

from .aggregates import Aggregates
from .alert_event_view import AlertEventView
from .alert_rule_body import AlertRuleBody
from .alert_rule_view import AlertRuleView
from .capabilities_output_body import CapabilitiesOutputBody
from .ci_report import CIReport
from .ci_report_analysis_type_0 import CIReportAnalysisType0
from .ci_report_baseline_error_type_0 import CIReportBaselineErrorType0
from .ci_report_baseline_side_type_0 import CIReportBaselineSideType0
from .ci_report_comparison import CIReportComparison
from .ci_report_comparison_context import CIReportComparisonContext
from .ci_report_comparison_error_type_0 import CIReportComparisonErrorType0
from .ci_report_comparison_info import CIReportComparisonInfo
from .ci_report_comparison_status import CIReportComparisonStatus
from .ci_report_comparison_tags import CIReportComparisonTags
from .ci_report_row_links import CIReportRowLinks
from .ci_report_run import CIReportRun
from .ci_report_run_run_tags import CIReportRunRunTags
from .ci_report_side import CIReportSide
from .ci_report_side_error_type_0 import CIReportSideErrorType0
from .ci_report_status import CIReportStatus
from .ci_report_summary import CIReportSummary
from .cli_exchange_input_body import CliExchangeInputBody
from .cli_exchange_output_body import CliExchangeOutputBody
from .cluster_info import ClusterInfo
from .cluster_info_info import ClusterInfoInfo
from .cluster_info_optional_info import ClusterInfoOptionalInfo
from .commit_type_0 import CommitType0
from .compare_analysis import CompareAnalysis
from .compare_result import CompareResult
from .compare_side import CompareSide
from .create_token_input_body import CreateTokenInputBody
from .create_token_output_body import CreateTokenOutputBody
from .error_detail import ErrorDetail
from .error_model import ErrorModel
from .get_ci_report_baseline import GetCiReportBaseline
from .git_hub_info import GitHubInfo
from .hardware import Hardware
from .health_output_body import HealthOutputBody
from .history_sample import HistorySample
from .history_series import HistorySeries
from .list_alert_events_output_body import ListAlertEventsOutputBody
from .list_alert_rules_output_body import ListAlertRulesOutputBody
from .list_commit_type_0 import ListCommitType0
from .list_tokens_output_body import ListTokensOutputBody
from .lookback_analysis_type_0 import LookbackAnalysisType0
from .machine_info import MachineInfo
from .me_output_body import MeOutputBody
from .pairwise_analysis_type_0 import PairwiseAnalysisType0
from .recent_run_list_item import RecentRunListItem
from .recent_run_list_item_run_tags import RecentRunListItemRunTags
from .recent_runs_page import RecentRunsPage
from .result_detail import ResultDetail
from .result_detail_change_annotations import ResultDetailChangeAnnotations
from .result_detail_context import ResultDetailContext
from .result_detail_error_type_0 import ResultDetailErrorType0
from .result_detail_info import ResultDetailInfo
from .result_detail_optional_benchmark_info_type_0 import (
    ResultDetailOptionalBenchmarkInfoType0,
)
from .result_detail_run_tags import ResultDetailRunTags
from .result_detail_tags import ResultDetailTags
from .result_detail_validation_type_0 import ResultDetailValidationType0
from .result_list_item import ResultListItem
from .result_list_item_run_tags import ResultListItemRunTags
from .result_page import ResultPage
from .series_list_item import SeriesListItem
from .series_list_item_context import SeriesListItemContext
from .series_list_item_status import SeriesListItemStatus
from .series_list_item_tags import SeriesListItemTags
from .series_page import SeriesPage
from .stats_input import StatsInput
from .submit_output_body import SubmitOutputBody
from .submit_request import SubmitRequest
from .submit_request_change_annotations_type_0 import (
    SubmitRequestChangeAnnotationsType0,
)
from .submit_request_context import SubmitRequestContext
from .submit_request_error import SubmitRequestError
from .submit_request_info import SubmitRequestInfo
from .submit_request_optional_benchmark_info_type_0 import (
    SubmitRequestOptionalBenchmarkInfoType0,
)
from .submit_request_run_tags import SubmitRequestRunTags
from .submit_request_tags import SubmitRequestTags
from .submit_request_validation_type_0 import SubmitRequestValidationType0
from .token_view import TokenView
from .update_result_input_body import UpdateResultInputBody
from .update_result_input_body_change_annotations_type_0 import (
    UpdateResultInputBodyChangeAnnotationsType0,
)
from .z_score_stats_type_0 import ZScoreStatsType0

__all__ = (
    "Aggregates",
    "AlertEventView",
    "AlertRuleBody",
    "AlertRuleView",
    "CapabilitiesOutputBody",
    "CIReport",
    "CIReportAnalysisType0",
    "CIReportBaselineErrorType0",
    "CIReportBaselineSideType0",
    "CIReportComparison",
    "CIReportComparisonContext",
    "CIReportComparisonErrorType0",
    "CIReportComparisonInfo",
    "CIReportComparisonStatus",
    "CIReportComparisonTags",
    "CIReportRowLinks",
    "CIReportRun",
    "CIReportRunRunTags",
    "CIReportSide",
    "CIReportSideErrorType0",
    "CIReportStatus",
    "CIReportSummary",
    "CliExchangeInputBody",
    "CliExchangeOutputBody",
    "ClusterInfo",
    "ClusterInfoInfo",
    "ClusterInfoOptionalInfo",
    "CommitType0",
    "CompareAnalysis",
    "CompareResult",
    "CompareSide",
    "CreateTokenInputBody",
    "CreateTokenOutputBody",
    "ErrorDetail",
    "ErrorModel",
    "GetCiReportBaseline",
    "GitHubInfo",
    "Hardware",
    "HealthOutputBody",
    "HistorySample",
    "HistorySeries",
    "ListAlertEventsOutputBody",
    "ListAlertRulesOutputBody",
    "ListCommitType0",
    "ListTokensOutputBody",
    "LookbackAnalysisType0",
    "MachineInfo",
    "MeOutputBody",
    "PairwiseAnalysisType0",
    "RecentRunListItem",
    "RecentRunListItemRunTags",
    "RecentRunsPage",
    "ResultDetail",
    "ResultDetailChangeAnnotations",
    "ResultDetailContext",
    "ResultDetailErrorType0",
    "ResultDetailInfo",
    "ResultDetailOptionalBenchmarkInfoType0",
    "ResultDetailRunTags",
    "ResultDetailTags",
    "ResultDetailValidationType0",
    "ResultListItem",
    "ResultListItemRunTags",
    "ResultPage",
    "SeriesListItem",
    "SeriesListItemContext",
    "SeriesListItemStatus",
    "SeriesListItemTags",
    "SeriesPage",
    "StatsInput",
    "SubmitOutputBody",
    "SubmitRequest",
    "SubmitRequestChangeAnnotationsType0",
    "SubmitRequestContext",
    "SubmitRequestError",
    "SubmitRequestInfo",
    "SubmitRequestOptionalBenchmarkInfoType0",
    "SubmitRequestRunTags",
    "SubmitRequestTags",
    "SubmitRequestValidationType0",
    "TokenView",
    "UpdateResultInputBody",
    "UpdateResultInputBodyChangeAnnotationsType0",
    "ZScoreStatsType0",
)
