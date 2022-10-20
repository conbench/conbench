from typing import Any, Dict, List

from benchrun import CaseList


class TestCaseList:
    def test_no_params(self) -> None:
        case_list = CaseList(params={})
        assert case_list.case_list == [{}]

    def test_one_param(self) -> None:
        case_list = CaseList(params={"foo": ["bar", "baz"]})
        assert case_list.case_list == [{"foo": "bar"}, {"foo": "baz"}]

    def test_two_params(self) -> None:
        case_list = CaseList(params={"foo": ["a", "b"], "bar": [1, 2]})
        assert case_list.case_list == [
            {"foo": "a", "bar": 1},
            {"foo": "a", "bar": 2},
            {"foo": "b", "bar": 1},
            {"foo": "b", "bar": 2},
        ]

    def test_negative_filter(self) -> None:
        class FilteredCaseList(CaseList):
            def filter_cases(
                self, case_list: List[Dict[str, Any]]
            ) -> List[Dict[str, Any]]:
                return [
                    case
                    for case in case_list
                    if not (case["foo"] == "a" and case["bar"] == 1)
                ]

        case_list = FilteredCaseList(params={"foo": ["a", "b"], "bar": [1, 2]})

        assert case_list.case_list == [
            {"foo": "a", "bar": 2},
            {"foo": "b", "bar": 1},
            {"foo": "b", "bar": 2},
        ]

    def test_positive_filter(self) -> None:
        class FilteredCaseList(CaseList):
            def filter_cases(
                self, case_list: List[Dict[str, Any]]
            ) -> List[Dict[str, Any]]:
                return [{"evil_laugh": "muahaha"}]

        case_list = FilteredCaseList(params={"foo": ["a", "b"], "bar": [1, 2]})

        assert case_list.case_list == [{"evil_laugh": "muahaha"}]
