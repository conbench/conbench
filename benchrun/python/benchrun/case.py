import itertools
from typing import Any, Dict, List


class CaseList:
    """
    A class to define a valid list of cases on which to run a benchmark from a set of
    valid values for each parameter.

    Attributes
    ----------

    params : Dict[str, list]
        A dict where keys are the parameter for a benchmark and values are a list of
        valid arguments for that parameter
    case_list : List[Dict[str, Any]]
        A list of cases, where each case is a dict where keys are parameters and
        values are an argument for each respective parameter
    """

    params: Dict[str, list] = None
    case_list: List[Dict[str, Any]]

    def __init__(self, params: Dict[str, list]) -> None:
        self.params = params

        crossed_case_list = [
            # each case a dict of scalars
            dict(zip(self.params.keys(), tup))
            # cross join of value lists
            for tup in itertools.product(*self.params.values())
        ]

        self.case_list = self.filter_cases(crossed_case_list)

    def filter_cases(self, case_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out invalid cases. This method takes a list of cases (dicts where keys
        are params and values are arguments), and returns a list of cases, possibly
        filtered down to valid combinations.

        By default, does not filter out any cases. Override this method to implement
        filtering. To specify only a specific set of cases which should be run, simply
        ignore the input and return that list of cases.

        Parameters
        ----------

        case_list : List[Dict[str, Any]]
            A list of cases, where each case is a dict where keys are parameters and
            values are arguments for a benchmark.

        Returns
        -------
        A case list structured the same as the input, but possibly with invalid
        combinations removed.
        """
        return case_list
