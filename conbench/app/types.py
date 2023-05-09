from dataclasses import dataclass
from typing import Optional


@dataclass
class HighlightInHistPlot:
    # The benchmark result ID
    bmrid: str
    # Displayed in the plot as legend item. E.g. "highlight (contender)"
    # Must be provided.
    highlight_name: str


@dataclass
class BokehPlotJSONOrError:
    # The following two properties are meant to be mutually exclusive
    jsondoc: Optional[str]
    reason_why_no_plot: Optional[str]
